"""SFD §5.18 — Modalités de sortie et visualisation.

Arbre de décision 3 étapes :
  Étape 0 — La réponse nécessite-t-elle autre chose que du texte ?
  Étape 1 — Un outil MCP connecté gère-t-il cette catégorie ?
  Étape 2 — L'utilisateur demande-t-il un fichier ?
  Étape 3 — Visualiseur inline (défaut)

Gated behind ODYSSEUS_OUTPUT_ROUTER kill-switch (default OFF).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from src.app_context import app_context


logger = logging.getLogger(__name__)

# Sorties materializees par OutputRouter.apply(). Relatif au CWD comme le
# reste du projet (data/ est gitignore) — resolu a l'appel, pas a l'import.
DEFAULT_OUTPUT_DIR = Path("data/outputs")

# ─── Kill-switch ────────────────────────────────────────────────────────


def output_router_enabled() -> bool:
    val = os.getenv("ODYSSEUS_OUTPUT_ROUTER", "on").strip().lower()
    return val in {"on", "1", "true", "yes"}


# ─── Types ──────────────────────────────────────────────────────────────


class OutputMode(str, Enum):
    TEXT_ONLY = "text_only"
    TEXT_INLINE = "text_inline"
    MCP_TOOL = "mcp_tool"
    FILE_DOWNLOAD = "file_download"
    VISUAL_INLINE = "visual_inline"


class DesignModule(str, Enum):
    DIAGRAM = "diagram"
    MOCKUP = "mockup"
    INTERACTIVE = "interactive"
    CHART = "chart"
    ART = "art"
    DATA_VIZ = "data_viz"


@dataclass
class OutputDecision:
    mode: OutputMode
    module: DesignModule | None = None
    mcp_tool: str | None = None
    file_extension: str | None = None
    reason: str = ""


# ─── Triggers ───────────────────────────────────────────────────────────

# Mots-clés qui déclenchent une visualisation
VISUAL_TRIGGERS: dict[DesignModule, list[str]] = {
    DesignModule.DIAGRAM: [
        "diagramme",
        "diagram",
        "schéma",
        "schema",
        "flowchart",
        "organigramme",
        "flux",
        "flow",
        "architecture",
        "séquence",
        "sequence",
        "graphe",
        "graph",
    ],
    DesignModule.CHART: [
        "graphique",
        "chart",
        "courbe",
        "plot",
        "histogramme",
        "pie chart",
        "bar chart",
        "camembert",
        "données",
        "data",
        "statistiques",
        "statistics",
        "comparaison",
        "comparison",
    ],
    DesignModule.MOCKUP: [
        "maquette",
        "mockup",
        "wireframe",
        "interface",
        "UI",
        "formulaire",
        "form",
        "écran",
        "screen",
        "page",
        "landing page",
        "app",
    ],
    DesignModule.DATA_VIZ: [
        "visualisation",
        "visualization",
        "carte",
        "map",
        "heatmap",
        "treemap",
        "sankey",
        "network",
    ],
}

# Signaux de demande de fichier
FILE_SIGNALS: list[str] = [
    "crée un fichier",
    "cree un fichier",
    "sauvegarde",
    "sauvegarder",
    "télécharge",
    "telecharge",
    "exporte",
    "exporter",
    "download",
    ".pdf",
    ".png",
    ".svg",
    ".html",
    ".csv",
    ".json",
    ".xlsx",
]

# Catégories → modules de design
CATEGORY_TO_MODULE: dict[str, DesignModule] = {
    "architecture": DesignModule.DIAGRAM,
    "flux": DesignModule.DIAGRAM,
    "diagramme": DesignModule.DIAGRAM,
    "graphique": DesignModule.CHART,
    "données": DesignModule.CHART,
    "data": DesignModule.CHART,
    "interface": DesignModule.MOCKUP,
    "ui": DesignModule.MOCKUP,
    "maquette": DesignModule.MOCKUP,
}


# ─── Router ─────────────────────────────────────────────────────────────


@dataclass
class OutputRouter:
    """Routeur de modalité de sortie selon l'arbre de décision SFD §5.18."""

    connected_mcp_tools: dict[str, str] = field(default_factory=dict)
    # {category: mcp_tool_name}

    def route(self, request: str, response_text: str) -> OutputDecision:
        """Détermine la modalité de sortie optimale.

        Étapes dans l'ordre, s'arrête à la première correspondance.
        """
        request_lower = request.lower()

        # Étape 0 : réponse purement textuelle ?
        if self._is_purely_textual(request):
            return OutputDecision(mode=OutputMode.TEXT_ONLY, reason="purely textual request")

        # Étape 1 : outil MCP connecté ?
        category = self._detect_category(request_lower)
        if category and category in self.connected_mcp_tools:
            return OutputDecision(
                mode=OutputMode.MCP_TOOL,
                mcp_tool=self.connected_mcp_tools[category],
                reason=f"MCP tool available for category '{category}'",
            )

        # Étape 2 : demande de fichier ?
        if self._is_file_request(request_lower):
            ext = self._detect_file_extension(request_lower)
            return OutputDecision(
                mode=OutputMode.FILE_DOWNLOAD,
                file_extension=ext,
                reason="explicit file request detected",
            )

        # Étape 3 : visualiseur inline ?
        module = self._detect_design_module(request_lower)
        if module and self._content_merits_visualization(response_text):
            return OutputDecision(
                mode=OutputMode.VISUAL_INLINE,
                module=module,
                reason=f"content merits {module.value} visualization",
            )

        # Défaut : texte
        return OutputDecision(mode=OutputMode.TEXT_ONLY, reason="no visual trigger detected")

    def apply(
        self,
        decision: OutputDecision,
        response_text: str,
        out_dir: Path | None = None,
    ) -> Path | None:
        """Exécute la décision et renvoie le fichier produit (None si rien).

        `route()` reste pur : décider et écrire sont deux gestes distincts, pour
        que le premier soit testable sans disque. C'est `apply()` qui donne à
        `OutputDecision` l'effet de bord qui manquait — jusque-là la décision
        était calculée puis loggée, donc P22 ne produisait aucun effet.

        Ne fait rien pour TEXT_ONLY (la réponse est déjà la sortie) ni pour
        MCP_TOOL (l'invocation appartient à l'appelant, qui détient la
        connexion). Retourne le chemin écrit, ou None.
        """
        if decision.mode is OutputMode.TEXT_ONLY or decision.mode is OutputMode.MCP_TOOL:
            return None
        if not response_text or not response_text.strip():
            return None

        target_dir = Path(out_dir) if out_dir is not None else DEFAULT_OUTPUT_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        ext = self._extension_for(decision)
        stem = self._slug_for(decision)
        path = self._unique_path(target_dir / f"{stem}{ext}", response_text)

        try:
            path.write_text(response_text, encoding="utf-8")
        except OSError as exc:
            # Rule 2: never fail silently. A decision that could not be
            # honoured must be visible, not look like a success.
            logger.warning("[p22] could not write %s output: %s", decision.mode.value, exc)
            return None

        logger.info("[p22] wrote %s output to %s", decision.mode.value, path)
        return path

    def _extension_for(self, decision: OutputDecision) -> str:
        if decision.file_extension:
            return decision.file_extension
        return {DesignModule.DIAGRAM: ".mmd", DesignModule.CHART: ".csv"}.get(decision.module, ".md")

    def _slug_for(self, decision: OutputDecision) -> str:
        if decision.module:
            return decision.module.value
        return decision.mode.value.replace("_", "-")

    def _unique_path(self, path: Path, content: str) -> Path:
        """Ne jamais écraser en silence : deux sorties de même nom sont deux
        sorties distinctes, et un écrasement destructif serait invisible."""
        if not path.exists() or path.read_text(encoding="utf-8") == content:
            return path
        for n in range(2, 100):
            candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")
            if not candidate.exists() or candidate.read_text(encoding="utf-8") == content:
                return candidate
        return path

    def _is_purely_textual(self, request: str) -> bool:
        """Vérifie si la demande est purement textuelle."""
        textual_patterns = [
            r"^(dis|dit|répète|repete|quoi|comment|pourquoi|quand|où|qui|quel)",
            r"^(explique|décris|decris|résume|resume|liste|donne)",
            r"\?$",
        ]
        for pattern in textual_patterns:
            if re.search(pattern, request, re.IGNORECASE):
                # Vérifier qu'aucun trigger visuel n'est présent
                for triggers in VISUAL_TRIGGERS.values():
                    for trigger in triggers:
                        if trigger in request.lower():
                            return False
                return True
        return False

    def _detect_category(self, request: str) -> str | None:
        """Détecte la catégorie de la demande."""
        for category, keywords in VISUAL_TRIGGERS.items():
            for keyword in keywords:
                if keyword in request:
                    return category.value
        return None

    def _is_file_request(self, request: str) -> bool:
        """Détecte une demande explicite de fichier."""
        for signal in FILE_SIGNALS:
            if signal in request:
                return True
        return False

    def _detect_file_extension(self, request: str) -> str | None:
        """Détecte l'extension de fichier demandée."""
        extensions = [".pdf", ".png", ".svg", ".html", ".csv", ".json", ".xlsx", ".md", ".py"]
        for ext in extensions:
            if ext in request:
                return ext
        return None

    def _detect_design_module(self, request: str) -> DesignModule | None:
        """Détecte le module de design approprié."""
        for category, triggers in VISUAL_TRIGGERS.items():
            for trigger in triggers:
                if trigger in request:
                    return category
        return None

    def _content_merits_visualization(self, content: str) -> bool:
        """Vérifie si le contenu mérite une visualisation."""
        # Contenu avec structure spatiale/séquentielle/systémique
        structural_signals = [
            r"├|└|│|─",  # ASCII tree
            r"graph\s+(TD|LR|RL|BT)",  # Mermaid
            r"sequenceDiagram",
            r"flowchart",
            r"```(mermaid|dot|graphviz)",
            r"\d+\s*(étapes|steps|phases|stages)",
            r"(tableau|table)\s+(comparatif|de\s+comparaison)",
        ]
        for signal in structural_signals:
            if re.search(signal, content, re.IGNORECASE):
                return True
        return False


# ─── Singleton ───────────────────────────────────────────────────────────

app_context.caches.router: OutputRouter | None = None


def get_output_router() -> OutputRouter:
    if app_context.caches.router is None:
        app_context.caches.router = OutputRouter()
    return app_context.caches.router
