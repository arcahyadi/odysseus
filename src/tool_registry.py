"""Central Tool Registry — every tool is a modular brick.

Loaded by the Decision Engine and the SFD orchestrator.
Combines phase-lock enforcement (config/phase-lock.yaml) with
modular tool brick discovery (config/tool-decision-tree.yaml).
"""

import logging
import socket
from typing import Callable
import threading
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# Racine du projet, ancrée sur ce module et non sur le CWD. `src/tool_registry.py`
# vit dans `<projet>/src/`, donc la racine est son parent. Un chemin relatif au CWD
# faisait dépendre le phase-lock du répertoire de lancement du process — et le
# singleton le figeait pour toute la durée de vie du process.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# PhaseContext — Per-session phase state
# ============================================================


class PhaseContext:
    """Contexte de phase actuel pour une session."""

    def __init__(self, phase: str = "BUILD", session_id: str | None = None):
        self.phase = phase.upper()
        self.session_id = session_id


# ============================================================
# ToolBrick — Modular tool brick for any phase
# ============================================================


class ToolBrick:
    """A modular tool brick that can be plugged into any phase."""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.type = config.get("type", "unknown")
        self.phases = config.get("phase", [])
        if isinstance(self.phases, str):
            self.phases = [self.phases]
        self.provides = config.get("provides", [])
        self.requires = config.get("requires", [])
        self.fallback = config.get("fallback", [])
        self.optional = config.get("optional", False)

    def is_available(self) -> bool:
        for dep in self.requires:
            if isinstance(dep, str) and ":" in dep:
                host, port = dep.split(":", 1)
                if self._check_port(host, int(port)):
                    continue
                if self.fallback:
                    return any(
                        self._check_port(*f.split(":", 1)) for f in self.fallback if isinstance(f, str) and ":" in f
                    )
                return False
        return True

    @staticmethod
    def _check_port(host: str, port: str | int) -> bool:
        try:
            port = int(port)
            s = socket.create_connection((host, port), timeout=2)
            s.close()
            return True
        except (OSError, ValueError):
            return False

    def __repr__(self):
        return (
            f"ToolBrick(name={self.name!r}, type={self.type!r}, "
            f"phases={self.phases!r}, available={self.is_available()})"
        )


# ============================================================
# ToolRegistry — Central registry combining phase-lock + bricks
# ============================================================


class ToolRegistry:
    """Central registry of all modular tool bricks with phase-lock enforcement.

    - Reads config/phase-lock.yaml for phase-based tool restrictions
    - Reads config/tool-decision-tree.yaml for tool capabilities and fallbacks
    - Thread-safe singleton

    FAIL-CLOSED. ``config/phase-lock.yaml`` est un contrôle de gouvernance : s'il est
    absent, illisible ou malformé, le registre ne doit surtout pas se rabattre sur une
    configuration permissive. Il ne le fait plus — voir ``_load_config`` et
    ``is_tool_allowed``.

    Les chemins sont ancrés sur le module (``_PROJECT_ROOT``), jamais sur le CWD du
    process. Un chemin relatif au CWD faisait dépendre le verrou du répertoire depuis
    lequel le process avait démarré, et le singleton le figeait pour toute la durée de
    vie du process : le premier appel sous un mauvais CWD désactivait le phase-lock
    pour toutes les requêtes suivantes, silencieusement.
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self, config_path: str | None = None, brick_path: str | None = None):
        self._config_path = Path(config_path) if config_path else _PROJECT_ROOT / "config" / "phase-lock.yaml"
        self._brick_path = Path(brick_path) if brick_path else _PROJECT_ROOT / "config" / "tool-decision-tree.yaml"
        self._config: dict = {}
        self._config_loaded = False
        self._config = self._load_config()
        self._session_phases: dict[str, PhaseContext] = {}
        self._session_lock = threading.Lock()

        # Tool brick index from decision tree
        self.tools: dict[str, ToolBrick] = {}
        self._brick_config: dict = {}
        self._build_brick_index()

    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── Config loading ────────────────────────────────────────

    def _load_config(self) -> dict:
        """Charge le phase-lock. En cas d'échec, on reste fermé, pas ouvert.

        Échecs traités comme tels : fichier absent, illisible, ou YAML invalide. Les trois
        tombaient auparavant sur ``{"phases": {"BUILD": {"blocked_tools": []}}}``, c'est-à-dire
        un registre où **plus rien n'est jamais bloqué** — et le ``logger.warning`` ne
        couvrait que les exceptions, pas un fichier simplement absent : le mode dégradé
        était donc entièrement silencieux.

        Retourne ``{}`` et positionne ``_config_loaded = False`` ; ``is_tool_allowed``
        refuse alors tout, et refuse de *lever* : le seul appelant
        (``src/tool_execution.py:625``) est enveloppé dans ``except Exception: pass``
        (« ne jamais bloquer le loop sur une erreur de phase-lock »), donc une exception
        ici serait avalée et l'outil s'exécuterait — un fail-**open**. Le refus doit
        passer par la valeur de retour, qu'aucun appelant ne peut transformer en
        permission.
        """
        try:
            path = Path(self._config_path)
            if not path.exists():
                raise FileNotFoundError(f"phase-lock introuvable : {path}")
            with open(path) as f:
                loaded = yaml.safe_load(f)
            if not isinstance(loaded, dict):
                raise ValueError(f"phase-lock malformé : racine {type(loaded).__name__}, dict attendu")
            # `phases` doit être une table de tables. Un scalaire y passerait le test de
            # véracité (`12` est truthy) puis lèverait un `AttributeError` sur le
            # `.get(phase, {})` plus tard — exception avalée par l'appelant, donc
            # transformée en permission. La forme se vérifie ici, une fois pour toutes.
            phases = loaded.get("phases")
            if not isinstance(phases, dict) or not phases:
                raise ValueError(f"phase-lock malformé : `phases` doit être une table non vide, vu {type(phases).__name__}")
            bad = [k for k, v in phases.items() if not isinstance(v, dict)]
            if bad:
                raise ValueError(f"phase-lock malformé : entrées de `phases` non-table : {bad[:5]}")
            self._config_loaded = True
            return loaded
        except Exception as e:
            self._config_loaded = False
            logger.critical(
                "PHASE-LOCK INDISPONIBLE — tous les outils seront REFUSÉS par sécurité "
                "(fail-closed). Cause : %s. Attendu : %s",
                e,
                self._config_path,
            )
            return {}

    @property
    def phase_lock_loaded(self) -> bool:
        """`False` quand le phase-lock n'a pas pu être chargé → tout est refusé.

        Exposé pour que le cockpit puisse afficher l'état du contrôle, plutôt que de
        le laisser se dégrader sans que personne ne le voie.
        """
        return self._config_loaded

    def _build_brick_index(self):
        try:
            path = Path(self._brick_path)
            if not path.exists():
                raise FileNotFoundError(f"decision tree introuvable : {path}")
            with open(path) as f:
                self._brick_config = yaml.safe_load(f)
        except Exception as e:
            # Index de capacités, pas un contrôle d'accès : l'effet d'un index vide est
            # « outil non découvert », pas « outil autorisé ». On le signale, mais on ne
            # bloque pas le process pour autant.
            logger.warning("tool-decision-tree.yaml not loaded: %s", e)
            self._brick_config = {"decision_tree": {"phases": {}, "tool_capabilities": {}, "fallback_chains": {}}}

        caps = self._brick_config.get("decision_tree", {}).get("tool_capabilities", {})
        for name, cfg in caps.items():
            self.tools[name] = ToolBrick(name, cfg)

    # ── Phase-lock API (existing callers) ─────────────────────

    def set_phase(self, session_id: str, phase: str) -> None:
        with self._session_lock:
            self._session_phases[session_id] = PhaseContext(phase, session_id)
            logger.info(f"Session {session_id}: phase → {phase.upper()}")

    def get_phase(self, session_id: str) -> str:
        with self._session_lock:
            ctx = self._session_phases.get(session_id)
            return ctx.phase if ctx else self._config.get("default_phase", "BUILD")

    def is_tool_allowed(self, tool_name: str, session_id: str, tool_args: dict = None) -> dict:
        # Fail-closed : sans phase-lock chargé, on ne peut rien autoriser. Ce contrôle
        # passe par la VALEUR DE RETOUR et jamais par une exception — voir `_load_config`
        # pour pourquoi (l'appelant avale les exceptions, ce qui ouvrirait la porte).
        if not self._config_loaded:
            return {
                "allowed": False,
                "reason": (
                    f"phase-lock indisponible — refus par défaut de {tool_name} "
                    f"(contrôle de gouvernance non chargé, voir phase_lock_loaded)"
                ),
                "phase": self.get_phase(session_id),
                "phase_lock_loaded": False,
            }

        phase = self.get_phase(session_id)
        phase_config = self._config.get("phases", {}).get(phase, {})
        blocked = phase_config.get("blocked_tools", [])

        if tool_name in blocked:
            return {
                "allowed": False,
                "reason": phase_config.get("message", f"Tool {tool_name} bloqué en phase {phase}"),
                "phase": phase,
            }

        if "write_restriction" in phase_config and tool_args:
            path = tool_args.get("path", tool_args.get("file_path", ""))
            if path:
                allowed_paths = phase_config["write_restriction"].get("allowed_paths", [])
                if not any(str(path).startswith(p) for p in allowed_paths):
                    return {
                        "allowed": False,
                        "reason": phase_config["write_restriction"].get(
                            "message", f"Écriture dans {path} non autorisée en phase {phase}"
                        ),
                        "phase": phase,
                    }

        if "exec_restriction" in phase_config and tool_name in ("bash", "python"):
            command = ""
            if tool_args:
                command = tool_args.get("command", tool_args.get("cmd", ""))
            patterns = phase_config["exec_restriction"].get("allowed_commands_patterns", [])
            if command and not any(p in command for p in patterns):
                return {
                    "allowed": False,
                    "reason": phase_config["exec_restriction"].get(
                        "message", f"Commande non autorisée en phase {phase}"
                    ),
                    "phase": phase,
                }

        return {"allowed": True, "reason": "ok", "phase": phase}

    def get_allowed_tools(self, all_tools: list, session_id: str) -> list:
        return [
            t
            for t in all_tools
            if self.is_tool_allowed(t.get("name", t) if isinstance(t, dict) else t, session_id)["allowed"]
        ]

    def get_phase_message(self, session_id: str = None) -> str:
        if session_id:
            phase = self.get_phase(session_id)
        else:
            phase = self._config.get("default_phase", "BUILD")
        phase_config = self._config.get("phases", {}).get(phase, {})
        return phase_config.get("message", f"Phase active : {phase}")

    # ── Tool brick API (decision tree) ────────────────────────

    def get_tools_for_phase(self, phase: str) -> list[ToolBrick]:
        dt = self._brick_config.get("decision_tree", {})
        phase_config = dt.get("phases", {}).get(phase, {})
        priority_order = phase_config.get("priority", [])
        optional_tools = set(phase_config.get("optional", []))
        tool_names = phase_config.get("tools", [])

        available = []
        for tool_name in tool_names:
            if tool_name in self.tools:
                brick = self.tools[tool_name]
                if brick.is_available() or tool_name in optional_tools:
                    available.append(brick)

        if priority_order:
            priority_set = {name: i for i, name in enumerate(priority_order)}
            available.sort(key=lambda b: priority_set.get(b.name, 999))
        return available

    def get_tool(self, name: str) -> ToolBrick | None:
        return self.tools.get(name)

    def get_all_available(self) -> dict[str, ToolBrick]:
        return {name: brick for name, brick in self.tools.items() if brick.is_available()}

    def get_fallback_chain(self, tool_name: str) -> list[str]:
        dt = self._brick_config.get("decision_tree", {})
        fallback_chains = dt.get("fallback_chains", {})
        return list(fallback_chains.get(tool_name, []))

    def get_gates_for_phase(self, phase: str) -> list[str]:
        dt = self._brick_config.get("decision_tree", {})
        phase_config = dt.get("phases", {}).get(phase, {})
        return list(phase_config.get("gates", []))

    def resolve_with_fallback(self, tool_name: str) -> ToolBrick | None:
        brick = self.tools.get(tool_name)
        if brick is None:
            return None
        if brick.is_available():
            return brick
        for fallback_name in self.get_fallback_chain(tool_name):
            fb = self.tools.get(fallback_name)
            if fb and fb.is_available():
                logger.info(f"Fallback: {tool_name} → {fallback_name}")
                return fb
        return None

    def __repr__(self):
        return f"ToolRegistry(tools={len(self.tools)}, available={len(self.get_all_available())})"


# ─── Décorateur d'auto-enregistrement (MOD-8) ───────────────

_registered_functions: dict[str, callable] = {}


def register(name: str):
    """Décorateur pour auto-enregistrer une fonction comme outil.
    
    Usage :
        @register("mon_outil")
        def mon_outil():
            return "ok"
    
    L'outil est enregistré dans le registre central (ToolRegistry.get_instance())
    SANS qu'il soit nécessaire d'importer routes.*.
    """
    def decorator(fn):
        registry = ToolRegistry.get_instance()
        registry.tools[name] = ToolBrick(name, {
            "type": "function",
            "phase": ["BUILD"],
            "provides": [name],
        })
        _registered_functions[name] = fn
        return fn
    return decorator


def get_registered_function(name: str) -> Callable | None:
    """Récupère une fonction enregistrée par @register."""
    return _registered_functions.get(name)


def get_all_registered() -> dict:
    """Retourne toutes les fonctions enregistrées via @register."""
    return dict(_registered_functions)
