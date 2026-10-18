"""SFD §5.5 — Exécution durable.

Couche séparée du raisonnement qui garantit qu'une action survit à une panne :
  - Workflows avec état persistant
  - Politiques de retry (max attempts, backoff exponentiel)
  - Compensation (pattern saga) — **ECHAFAUDAGE, jamais arme** (v11 §1) :
    le declencheur est cable (2 appelants), mais aucune construction de
    WorkflowStep ne fournit `compensation=` (0 dans tout le depot, defaut
    None a `:88`) et la branche journalise puis passe a COMPENSATED sans
    rien executer. Ce n'est donc pas une capacite : c'est un crochet.
  - Points d'approbation humaine longue durée

Gated behind ODYSSEUS_DURABLE_EXECUTION kill-switch (default OFF).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from src.app_context import app_context


logger = logging.getLogger(__name__)

# ─── Kill-switch ────────────────────────────────────────────────────────


def durable_execution_enabled() -> bool:
    val = os.getenv("ODYSSEUS_DURABLE_EXECUTION", "on").strip().lower()
    return val in {"on", "1", "true", "yes"}


# ─── Constants ──────────────────────────────────────────────────────────

# Ancré sur le module, jamais sur le CWD. Un chemin relatif au CWD faisait dépendre la
# reprise d'un crash du répertoire depuis lequel le process avait démarré : le fichier
# écrit par le process d'avant n'était simplement pas trouvé par le suivant, et le run
# repartait de zéro — une reprise qui ne survit pas au crash qu'elle est censée traiter.
# `data/` est gitignoré, donc rien de persistant n'est exposé.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = _PROJECT_ROOT / "data" / "workflows"

# Clé sous laquelle la conversation en cours est rangée dans `WorkflowState.context`.
RUN_MESSAGES_KEY = "messages"


# ─── Types ──────────────────────────────────────────────────────────────


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    WAITING_APPROVAL = "waiting_approval"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    COMPENSATING = "compensating"


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    max_delay_seconds: float = 60.0

    def delay_for_attempt(self, attempt: int) -> float:
        delay = self.base_delay_seconds * (self.backoff_multiplier ** (attempt - 1))
        return min(delay, self.max_delay_seconds)


@dataclass
class WorkflowStep:
    name: str
    action: str  # Callable name or function reference
    compensation: str | None = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0
    result: Any | None = None
    error: str | None = None
    started_at: float = 0.0
    completed_at: float = 0.0
    requires_approval: bool = False
    approved: bool = False


@dataclass
class WorkflowState:
    id: str
    name: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    steps: list[WorkflowStep] = field(default_factory=list)
    current_step: int = 0
    context: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


# ─── Workflow Engine ────────────────────────────────────────────────────


class DurableExecutor:
    """Moteur d'exécution durable avec persistance et retry."""

    def __init__(self):
        self.running: dict[str, WorkflowState] = {}

    def create_workflow(self, name: str, steps: list[WorkflowStep], context: dict | None = None) -> WorkflowState:
        wf = WorkflowState(
            id=str(uuid.uuid4()),
            name=name,
            steps=steps,
            context=context or {},
        )
        self._save(wf)
        return wf

    async def execute(self, wf: WorkflowState, step_functions: dict[str, Callable]) -> WorkflowState:
        """Exécute un workflow du début à la fin avec reprise après panne."""
        wf.status = WorkflowStatus.RUNNING
        self._save(wf)

        while wf.current_step < len(wf.steps):
            step = wf.steps[wf.current_step]

            # Reprise : sauter les étapes déjà complétées
            if step.status == StepStatus.COMPLETED:
                wf.current_step += 1
                continue

            # Approbation humaine
            if step.requires_approval and not step.approved:
                step.status = StepStatus.WAITING_APPROVAL
                wf.status = WorkflowStatus.PAUSED
                self._save(wf)
                logger.info("Workflow %s waiting approval for step '%s'", wf.id, step.name)
                return wf  # L'exécution reprendra après approbation

            # Exécuter l'étape avec retry
            step.status = StepStatus.RUNNING
            step.started_at = time.time()
            self._save(wf)

            func = step_functions.get(step.action)
            if func is None:
                step.status = StepStatus.FAILED
                step.error = f"Unknown action: {step.action}"
                await self._handle_step_failure(wf, step)
                continue

            success = False
            for attempt in range(1, step.retry_policy.max_attempts + 1):
                step.attempts = attempt
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(wf.context, **wf.context)
                    else:
                        result = func(wf.context, **wf.context)
                    step.result = result
                    step.status = StepStatus.COMPLETED
                    step.completed_at = time.time()
                    success = True
                    break
                except Exception as e:
                    step.error = str(e)
                    if attempt < step.retry_policy.max_attempts:
                        delay = step.retry_policy.delay_for_attempt(attempt)
                        logger.warning(
                            "Step '%s' attempt %d failed: %s. Retrying in %.1fs", step.name, attempt, e, delay
                        )
                        await asyncio.sleep(delay)

            if not success:
                step.status = StepStatus.FAILED
                await self._handle_step_failure(wf, step)
                return wf

            wf.current_step += 1
            wf.updated_at = time.time()
            self._save(wf)

        wf.status = WorkflowStatus.COMPLETED
        wf.updated_at = time.time()
        self._save(wf)
        return wf

    async def _handle_step_failure(self, wf: WorkflowState, failed_step: WorkflowStep) -> None:
        """Crochet de compensation (pattern saga) — **n'execute rien** (v11 §1).

        La compensation d'un saga se declenche bien ici, sur deux appelants
        reels (`:161`, `:188`). Ce que ce crochet ne fait pas : executer une
        compensation. Il parcourt les etapes en sens inverse, journalise
        `"Compensating step ..."` et passe le statut a `COMPENSATED`.

        Et rien ne l'arme : `WorkflowStep.compensation` vaut `None` par defaut
        (`:88`) et aucune construction du depot ne fournit `compensation=`.
        La branche `if step.compensation:` n'est donc jamais prise.

        Le nom de la methode dit son declencheur, pas son action — c'est
        precisement pour cela qu'une recherche par nom de symbole conclut a
        tort que la compensation est absente.
        """
        wf.status = WorkflowStatus.COMPENSATING
        self._save(wf)

        # Compenser dans l'ordre inverse
        for i in range(wf.current_step - 1, -1, -1):
            step = wf.steps[i]
            if step.compensation:
                step.status = StepStatus.COMPENSATING
                self._save(wf)
                logger.info("Compensating step '%s': %s", step.name, step.compensation)
                step.status = StepStatus.COMPENSATED
                self._save(wf)

        wf.status = WorkflowStatus.FAILED
        self._save(wf)

    def approve_step(self, wf: WorkflowState, step_index: int) -> bool:
        """Approuve une étape en attente d'approbation humaine."""
        if step_index >= len(wf.steps):
            return False
        step = wf.steps[step_index]
        if step.status != StepStatus.WAITING_APPROVAL:
            return False
        step.approved = True
        wf.status = WorkflowStatus.RUNNING
        self._save(wf)
        return True

    def resume(self, workflow_id: str) -> WorkflowState | None:
        """Charge un workflow depuis le disque pour reprise après panne.

        Charge par **id de workflow** (`<uuid>.json`). Pour retrouver un run par session,
        utiliser `resume_session()` — passer un id de session ici rend toujours `None`.
        """
        path = WORKFLOW_DIR / f"{workflow_id}.json"
        if not path.exists():
            return None
        return self._from_dict(json.loads(path.read_text()))

    # ─── Cycle de vie d'un run de boucle (P14 / UC-02 / UC-11) ────────────
    #
    # `create_workflow`/`resume` sont corrects mais n'étaient appelés par personne : rien
    # n'était donc jamais persisté, et le seul appelant de `resume()` (M6.3) le faisait
    # APRÈS la boucle de rounds, dans une section qui ne pouvait rien restaurer. Les
    # trois méthodes ci-dessous donnent enfin au module un cycle de vie utilisable par la
    # boucle : ouvrir un run, avancer son curseur, le clore.
    #
    # Le workflow d'un run n'a **aucune étape** : le nombre de tours n'est pas connu à
    # l'avance, et `WorkflowStep` n'a pas grand sens pour un tour de LLM. Ce qui est
    # suivi, c'est `current_step` comme curseur de round et `context` comme conversation.

    def save(self, wf: WorkflowState) -> None:
        """Persistance publique — même écriture que `_save`, pour les appelants externes."""
        self._save(wf)

    def resume_session(self, session_id: str) -> WorkflowState | None:
        """Retrouve le run d'une session, le plus récent ET encore reprenable.

        `resume()` charge par **id de workflow** (`<uuid>.json`) ; il ne peut donc pas
        servir à retrouver un run par session. C'est le troisième défaut du reliquat R2 :
        l'ancien appelant passait un id de session là où un id de workflow était attendu,
        donc `path.exists()` était toujours `False` et `resume()` rendait toujours `None`
        — même si un fichier avait existé. Deux raisons indépendantes pour le même
        symptôme, qu'il fallait mesurer séparément.

        Le plus récent l'emporte (`updated_at`) : plusieurs runs d'une même session
        peuvent coexister sur disque tant que la rétention n'a pas tourné, et reprendre
        le plus ancien reviendrait ressusciter un état périmé.
        """
        if not WORKFLOW_DIR.is_dir():
            return None
        candidates: list[WorkflowState] = []
        for path in WORKFLOW_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text())
            except (OSError, ValueError):
                # Un fichier illisible ou tronqué ne doit pas empêcher la reprise des
                # autres : c'est le même état qu'un fichier absent pour ce run-là.
                continue
            if data.get("name") != session_id:
                continue
            try:
                wf = self._from_dict(data)
            except (KeyError, ValueError, TypeError):
                continue
            if self.is_resumable(wf):
                candidates.append(wf)
        if not candidates:
            return None
        return max(candidates, key=lambda w: w.updated_at or w.created_at)

    def _prune_session(self, session_id: str, keep_id: str) -> int:
        """Ne garde que le run le plus récent d'une session. Retourne le nombre supprimé.

        Une session n'a jamais besoin de plusieurs runs reprenables : un seul état
        « courant » suffit. Sans cette rétention, ce module — qui jusqu'ici n'écrivait
        rien du tout, faute d'appelant — laisserait un fichier JSON par tour et par
        session, et `resume_session` deviendrait un parcours du répertoire à chaque tour.

        Les fichiers ne sont supprimés qu'après lecture et contrôle de `name` : on ne
        touche jamais un fichier dont on n'a pas vérifié qu'il appartient à cette session.
        """
        if not WORKFLOW_DIR.is_dir():
            return 0
        removed = 0
        for path in WORKFLOW_DIR.glob("*.json"):
            if path.stem == keep_id:
                continue
            try:
                data = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            if data.get("name") != session_id:
                continue
            try:
                path.unlink()
                removed += 1
            except OSError as e:
                logger.debug("workflow ancien non supprimé (%s) : %s", path.name, e)
        return removed

    @staticmethod
    def _from_dict(data: dict) -> WorkflowState:
        return WorkflowState(
            id=data["id"],
            name=data["name"],
            status=WorkflowStatus(data["status"]),
            steps=[WorkflowStep(**s) for s in data["steps"]],
            current_step=data["current_step"],
            context=data.get("context", {}),
            created_at=data.get("created_at", 0),
            updated_at=data.get("updated_at", 0),
        )

    @staticmethod
    def is_resumable(wf: WorkflowState) -> bool:
        """Un run interrompu reprend ; un run terminé ne ressuscite pas.

        `COMPLETED`/`FAILED` sont donc volontairement exclus. Sans cette borne, le tour
        suivant de l'utilisateur repartirait indéfiniment d'une conversation vieille, et
        le mot « reprise » désignerait une régression : l'agent n'oublerait jamais l'il
        s'agit d'une nouvelle demande.
        """
        if wf.status not in (WorkflowStatus.RUNNING, WorkflowStatus.PAUSED):
            return False
        return bool(wf.context.get(RUN_MESSAGES_KEY))

    def begin_run(
        self, session_id: str, messages: list, *, enabled: bool | None = None
    ) -> tuple[WorkflowState | None, bool]:
        """Ouvre un run, ou reprend celui qui a été interrompu.

        Retourne `(workflow, repris)`. `workflow is None` quand la persistance est
        éteinte — et dans ce cas rien n'est écrit du tout.

        `messages` doit être sérialisable en JSON, ce qui est le cas des messages OpenAI
        (du JSON pur). Un contenu non sérialisable ferait échouer `_save` ; l'appelant
        traite l'échec, donc un message exotique ne casse pas le run.
        """
        is_enabled = durable_execution_enabled() if enabled is None else bool(enabled)
        if not is_enabled:
            return None, False

        existing = self.resume_session(session_id)
        if existing is not None:
            existing.status = WorkflowStatus.RUNNING
            self._save(existing)
            return existing, True

        created = self.create_workflow(session_id, steps=[], context={RUN_MESSAGES_KEY: messages})
        created.status = WorkflowStatus.RUNNING
        self._save(created)
        self._prune_session(session_id, created.id)
        return created, False

    def record_progress(self, wf: WorkflowState, next_round: int, messages: list) -> None:
        """Enregistre la conversation et le round **à jouer ensuite**.

        `next_round` est le round suivant, pas le round qui vient d'être joué : le curseur
        doit désigner le travail restant, sinon la reprise rejouerait un round déjà
        terminé. `next_round == 1` signifie « rien d'accompli, on démarre ».

        Appelé en fin de round. Un crash au milieu du round N laisse donc le curseur à N,
        et la reprise rejoue N — un tour de LLM n'étant pas idempotent, un tour à moitié
        exécuté ne doit pas être compté comme acquis.
        """
        wf.current_step = next_round
        wf.updated_at = time.time()
        wf.context[RUN_MESSAGES_KEY] = messages
        self._save(wf)

    @staticmethod
    def is_continuation(incoming: list, persisted: list) -> bool:
        """Vrai si la conversation entrante est un **préfixe** de celle persistée.

        C'est le test qui distingue « le client se reconnecte et rejoue le même run » de
        « l'utilisateur a posé une nouvelle question ». Sans lui, une reprise écrase la
        nouvelle question par l'ancienne conversation : la saisie de l'utilisateur
        disparaît, silencieusement. Un préfixe est la signature d'un client qui renvoie
        ce qu'il avait lui-même envoyé et qui a progressé plus loin que lui.

        Une conversation entrante qui diverge — ou qui est plus longue que la persistée,
        cas où le client a ajouté des messages que le serveur n'a jamais vus — n'est pas
        une continuation : le run repris ne doit pas l'écraser.
        """
        if not persisted:
            return False
        if len(incoming) > len(persisted):
            return False
        return list(incoming) == list(persisted[: len(incoming)])

    def restart_run(self, session_id: str, messages: list) -> WorkflowState:
        """Abandonne le run reprenable de la session et en ouvre un neuf.

        Utilisé quand la conversation entrante n'est PAS une continuation de l'état
        persisté : plutôt que de laisser un état périmé composer la conversation suivante, on le clôture en
        `FAILED` — l'honnêteté est de dire qu'il n'a pas abouti, pas de le faire passer
        pour un run Compatible.
        """
        existing = self.resume_session(session_id)
        if existing is not None:
            existing.status = WorkflowStatus.FAILED
            self._save(existing)
        created = self.create_workflow(session_id, steps=[], context={RUN_MESSAGES_KEY: messages})
        created.status = WorkflowStatus.RUNNING
        self._save(created)
        self._prune_session(session_id, created.id)
        return created

    def finish_run(self, wf: WorkflowState, status: WorkflowStatus, messages: list | None = None) -> None:
        """Clôt un run pour qu'il ne soit plus repris.

        À appeler seulement quand le run va vraiment au bout. Si le générateur est
        interrompu par le client, le run reste `RUNNING` — c'est ce qui le rend reprenable
        au lancement suivant.

        `messages` permet d'y ranger la conversation finale : les sorties de boucle
        (`break` sur budget ou attente utilisateur) passent par là, et l'état de fin
        serait sinon celui du dernier début de round.
        """
        if messages is not None:
            wf.context[RUN_MESSAGES_KEY] = messages
        wf.status = status
        wf.updated_at = time.time()
        self._save(wf)
        self._prune_session(wf.name, wf.id)

    def _save(self, wf: WorkflowState) -> None:
        """Persiste l'état du workflow sur disque.

        Le répertoire est créé ici, et plus au moment de l'import : un `mkdir` à l'import
        est un effet de bord qui s'exécute dès que le module est chargé, y compris dans
        un simple `python -c "import ..."`. `data/` étant gitignoré, le créer au premier
        besoin suffit.
        """
        WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
        path = WORKFLOW_DIR / f"{wf.id}.json"
        data = {
            "id": wf.id,
            "name": wf.name,
            "status": wf.status.value,
            "steps": [
                {
                    "name": s.name,
                    "action": s.action,
                    "compensation": s.compensation,
                    "retry_policy": {
                        "max_attempts": s.retry_policy.max_attempts,
                        "base_delay_seconds": s.retry_policy.base_delay_seconds,
                        "backoff_multiplier": s.retry_policy.backoff_multiplier,
                        "max_delay_seconds": s.retry_policy.max_delay_seconds,
                    },
                    "status": s.status.value,
                    "attempts": s.attempts,
                    "result": s.result,
                    "error": s.error,
                    "started_at": s.started_at,
                    "completed_at": s.completed_at,
                    "requires_approval": s.requires_approval,
                    "approved": s.approved,
                }
                for s in wf.steps
            ],
            "current_step": wf.current_step,
            "context": wf.context,
            "created_at": wf.created_at,
            "updated_at": wf.updated_at,
        }
        path.write_text(json.dumps(data, indent=2))


# ─── Singleton ───────────────────────────────────────────────────────────

app_context.caches.executor: DurableExecutor | None = None


def get_durable_executor() -> DurableExecutor:
    if app_context.caches.executor is None:
        app_context.caches.executor = DurableExecutor()
    return app_context.caches.executor
