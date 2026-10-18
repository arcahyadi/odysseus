"""MultiAgentWorkflow — pipeline multi-agent complet avec modèles par rôle, cockpit live, et événements UI.

Chaque agent reçoit :
  - Un modèle adapté à son rôle (strong pour planner, standard pour executor, fast pour verifier)
  - Des outils spécifiques à sa mission
  - Le contexte accumulé des phases précédentes

Le workflow émet des événements SSE que le frontend affiche en temps réel :
  - workflow_start / phase_start / agent_result / phase_complete / workflow_complete
  - run_status (cockpit) à chaque transition
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from src.orchestrator.phases import CANONICAL_SEQUENCE, Phase

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════

# ── Modèle par rôle ────────────────────────────────────────────────────
# Chaque rôle utilise un tier de modèle différent.
# "strong"  → deep/reasoning (planner, researcher)
# "standard"→ default/utility (executor)
# "fast"    → quick/cheap (verifier, debate, security, constitution)
MODEL_TIER_BY_ROLE: dict[str, str] = {
    "constitution": "fast",
    "planner": "strong",
    "researcher": "strong",
    "executor": "standard",
    "debugger": "standard",
    "debate": "fast",
    "security": "fast",
    "verifier": "fast",
    "edgecase": "fast",
    "roadmapper": "standard",
}

# ── Tool sets par rôle ─────────────────────────────────────────────────
TOOLS_BY_ROLE: dict[str, list[str]] = {
    "constitution": ["read_file", "grep", "glob", "ls", "web_search", "web_fetch"],
    "planner": ["read_file", "grep", "glob", "ls", "write_file", "web_search", "web_fetch"],
    "researcher": ["web_search", "web_fetch", "read_file", "grep", "glob", "ls"],
    "executor": [
        "bash",
        "python",
        "write_file",
        "edit_file",
        "read_file",
        "grep",
        "glob",
        "ls",
        "web_search",
        "web_fetch",
    ],
    "debugger": ["bash", "python", "read_file", "grep", "glob", "ls"],
    "debate": ["read_file", "grep", "glob", "ls", "web_search"],
    "security": ["read_file", "grep", "glob", "ls", "bash", "web_search"],
    "verifier": ["bash", "python", "read_file", "grep", "glob", "ls"],
    "edgecase": ["read_file", "grep", "glob", "web_search"],
    "roadmapper": ["write_file", "read_file", "grep", "glob", "manage_memory", "update_plan"],
}

# ── Phase → agent(s) ───────────────────────────────────────────────────
PHASE_AGENTS: dict[Phase, list[str]] = {
    Phase.CLASSIFY: ["constitution"],
    Phase.KNOW: [],
    Phase.PLAN: ["planner", "researcher"],
    Phase.BUILD: ["executor"],
    Phase.QUALITY: ["debate", "security"],
    Phase.AUTOEVAL: ["verifier", "edgecase"],
    Phase.MEMORY_OBSERVE: ["roadmapper"],
}

# ── System prompts par rôle ────────────────────────────────────────────
ROLE_PROMPTS: dict[str, str] = {
    "constitution": (
        "Tu es l'agent Constitution. Ta mission : classifier le risque de "
        "l'objectif utilisateur selon les 10 invariants AgentOS. "
        "Produis un rapport concis : niveau de risque (LOW/MEDIUM/HIGH/CRITICAL), "
        "invariants concernés, et recommandations. Ne modifie rien."
    ),
    "planner": (
        "Tu es l'agent Planner. Ta mission : créer un plan d'exécution détaillé "
        "pour l'objectif. Décompose en étapes atomiques. Pour chaque étape, "
        "indique les fichiers à créer/modifier et les outils nécessaires. "
        "Écris le plan dans .planning/ si nécessaire."
    ),
    "researcher": (
        "Tu es l'agent Researcher. Ta mission : rechercher les meilleures "
        "approches, bibliothèques, patterns pour l'objectif. "
        "Fournis des recommandations concrètes avec des exemples de code. "
        "Utilise web_search et web_fetch pour trouver des solutions à jour."
    ),
    "executor": (
        "Tu es l'agent Executor. Ta mission : implémenter l'objectif étape par "
        "étape en suivant le plan. Utilise bash pour exécuter des commandes, "
        "write_file pour créer des fichiers, edit_file pour les modifier. "
        "Crée d'abord les dossiers avec bash mkdir avant d'écrire dedans. "
        "À chaque étape, vérifie que le code fonctionne avant de passer à la suite."
    ),
    "debugger": (
        "Tu es l'agent Debugger. Ta mission : diagnostiquer et corriger les "
        "erreurs rencontrées par l'executor. Utilise la méthode scientifique : "
        "isole le problème, formule une hypothèse, teste, corrige."
    ),
    "debate": (
        "Tu es l'agent Debate (5 personas). Ta mission : challenger le code "
        "produit sous 5 angles (Architecture, Sécurité, Performance, UX, Devil's advocate). "
        "Produis un verdict GO/CAUTION/STOP avec les raisons pour chaque angle."
    ),
    "security": (
        "Tu es l'agent Security Audit. Ta mission : auditer le code selon "
        "STRIDE + OWASP Top 10. Pour chaque vulnérabilité trouvée, indique "
        "la sévérité et propose un fix concret. Ne modifie pas le code toi-même."
    ),
    "verifier": (
        "Tu es l'agent Verifier. Ta mission : exécuter les tests et vérifier "
        "que l'objectif est atteint. Lance pytest, npm test, ou les commandes "
        "appropriées. Si des tests échouent, documente précisément lesquels et pourquoi."
    ),
    "edgecase": (
        "Tu es l'agent Edge-Case Generator. Ta mission : générer des cas limites "
        "pour le code produit (entrées vides, très longues, nulles, négatives, "
        "concurrentes...). Produis une liste de scénarios de test."
    ),
    "roadmapper": (
        "Tu es l'agent Roadmapper. Ta mission : mettre à jour la roadmap du projet "
        "(.planning/ROADMAP.md, STATE.md) avec les résultats du run. "
        "Documente ce qui a été fait, les décisions prises, et les prochaines étapes."
    ),
}

# ── Tier → endpoint prefix ─────────────────────────────────────────────
# Mapping des tiers de modèle vers les préfixes de resolve_endpoint
TIER_TO_PREFIX: dict[str, str] = {
    "strong": "utility",  # modèle fort
    "standard": "default",  # modèle standard
    "fast": "utility",  # fallback → utility (moins cher)
}


# ══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class AgentResult:
    agent: str
    role: str
    phase: str
    model: str = ""
    output: str = ""
    success: bool = True
    error: str = ""


@dataclass
class PhaseReport:
    phase: str
    agents: list[AgentResult] = field(default_factory=list)
    summary: str = ""


@dataclass
class WorkflowReport:
    objective: str
    phases: list[PhaseReport] = field(default_factory=list)
    final_output: str = ""
    success: bool = False


# ══════════════════════════════════════════════════════════════════════════
# WORKFLOW
# ══════════════════════════════════════════════════════════════════════════


class MultiAgentWorkflow:
    """Pipeline multi-agent 7 phases avec modèles par rôle et cockpit live."""

    def __init__(self, session_id: str, objective: str, model: str | None = None, registry=None):
        self.session_id = session_id
        self.objective = objective
        self.model = model
        self._registry = registry
        self._context: list[dict] = []
        self._phase_results: dict[str, PhaseReport] = {}
        self._phase_count = len([p for p in CANONICAL_SEQUENCE if PHASE_AGENTS.get(p)])

    # ── API publique ───────────────────────────────────────────────────

    async def run(self) -> AsyncGenerator[dict, None]:
        """Exécute le workflow complet et yield les événements SSE."""
        yield {
            "type": "workflow_start",
            "objective": self.objective[:200],
            "phases": [p.value for p in CANONICAL_SEQUENCE],
            "total_phases": self._phase_count,
        }

        report = WorkflowReport(objective=self.objective)
        completed = 0

        for phase in CANONICAL_SEQUENCE:
            agent_names = PHASE_AGENTS.get(phase, [])
            if not agent_names:
                yield {"type": "phase_skip", "phase": phase.value}
                continue

            completed += 1
            yield {
                "type": "phase_start",
                "phase": phase.value,
                "agents": agent_names,
                "progress": f"{completed}/{self._phase_count}",
                "message": f"🔵 Phase {phase.value} — {', '.join(agent_names)}",
            }

            # Cockpit : mise à jour live
            yield self._cockpit_event(phase, "running")

            phase_report = PhaseReport(phase=phase.value)

            # Lancer tous les agents de cette phase EN PARALLÈLE
            tasks = [self._run_agent(name, phase) for name in agent_names]
            results: list[AgentResult] = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    result = AgentResult(
                        agent=agent_names[i],
                        role=agent_names[i],
                        phase=phase.value,
                        success=False,
                        error=str(result),
                    )
                phase_report.agents.append(result)

                # Événement UI par agent
                yield {
                    "type": "agent_result",
                    "phase": phase.value,
                    "agent": result.agent,
                    "model": result.model,
                    "success": result.success,
                    "message": (
                        f"{'✅' if result.success else '❌'} {result.agent} ({result.model}) — {result.output[:150]}"
                    ),
                    "output_preview": result.output[:300] if result.output else "",
                    "error": result.error,
                }

            # Résumé et contexte
            phase_summary = self._summarize_phase(phase_report)
            phase_report.summary = phase_summary
            self._phase_results[phase.value] = phase_report
            self._context.append(
                {
                    "role": "system",
                    "content": f"[PHASE {phase.value} COMPLÉTÉE]\n{phase_summary}",
                }
            )

            yield {
                "type": "phase_complete",
                "phase": phase.value,
                "summary": phase_summary[:500],
                "message": f"✅ Phase {phase.value} terminée",
            }

            # Cockpit : phase done
            yield self._cockpit_event(phase, "completed")

            report.phases.append(phase_report)

        # Synthèse finale
        final = await self._synthesize(report)
        report.final_output = final
        report.success = True

        yield {
            "type": "workflow_complete",
            "final_output": final,
            "phases_completed": len(report.phases),
            "message": f"🎉 Workflow terminé — {len(report.phases)} phases complétées",
        }

        yield self._cockpit_event(None, "done")

    # ── Interne ────────────────────────────────────────────────────────

    def _cockpit_event(self, phase: Phase | None, status: str) -> dict:
        """Construit un événement cockpit (run_status)."""
        return {
            "type": "run_status",
            "phase": phase.value if phase else "done",
            "phase_active": True,
            "drift": "low",
            "iters": {"used": 0, "max": self._phase_count},
            "budget": None,
            "workflow_status": status,
        }

    async def _run_agent(self, agent_name: str, phase: Phase) -> AgentResult:
        """Exécute un agent avec modèle dédié + outils + contexte."""
        role = agent_name
        tools = TOOLS_BY_ROLE.get(role, ["read_file", "grep", "glob", "ls"])
        system_prompt = ROLE_PROMPTS.get(role, f"Tu es l'agent {agent_name}.")
        model_tier = MODEL_TIER_BY_ROLE.get(role, "standard")
        resolved_model = self._resolve_model_for_tier(model_tier)

        try:
            full_prompt = self._load_agent_prompt(agent_name)
            if full_prompt:
                system_prompt = full_prompt

            messages = [
                {"role": "system", "content": system_prompt},
                *self._context[-6:],
                {
                    "role": "user",
                    "content": (
                        f"OBJECTIF : {self.objective}\n\n"
                        f"Phase : {phase.value} | Rôle : {role} | Modèle : {resolved_model}\n"
                        f"Outils : {', '.join(tools)}\n"
                        f"Exécute ta mission. Sois concis et actionnable."
                    ),
                },
            ]

            logger.info(
                "[MultiAgent] %s | tier=%s model=%s tools=%d",
                agent_name,
                model_tier,
                resolved_model,
                len(tools),
            )

            result_text = await self._call_llm_with_tools(
                messages,
                tools,
                resolved_model,
            )

            return AgentResult(
                agent=agent_name,
                role=role,
                phase=phase.value,
                model=resolved_model,
                output=result_text,
                success=True,
            )

        except Exception as exc:
            logger.warning("[MultiAgent] %s failed: %s", agent_name, exc)
            return AgentResult(
                agent=agent_name,
                role=role,
                phase=phase.value,
                model=resolved_model,
                success=False,
                error=str(exc),
            )

    def _resolve_model_for_tier(self, tier: str) -> str:
        """Résout un modèle pour un tier donné (strong/standard/fast)."""
        try:
            from src.endpoint_resolver import resolve_endpoint

            prefix = TIER_TO_PREFIX.get(tier, "default")
            url, model, _ = resolve_endpoint(prefix, owner=self.session_id)
            return model or "unknown"
        except Exception:
            return "unknown"

    async def _call_llm_with_tools(self, messages: list, tool_names: list, preferred_model: str = "") -> str:
        """Appel LLM multi-turn avec exécution réelle d'outils (jusqu'à 5 tours)."""
        from src.agent_tools import ToolBlock
        from src.task_endpoint import resolve_task_candidates
        from src.tool_execution import execute_tool_block
        from src.tool_schemas import FUNCTION_TOOL_SCHEMAS

        candidates = resolve_task_candidates(owner=self.session_id)
        if not candidates:
            return "[Erreur: aucun endpoint LLM disponible]"

        # Utiliser le modèle préféré si dispo, sinon le premier candidat
        url, model, headers = candidates[0]
        if preferred_model and preferred_model != "unknown":
            model = preferred_model

        # Filtrer les schémas d'outils
        allowed_tools = set(tool_names)
        tool_schemas = [
            s
            for s in FUNCTION_TOOL_SCHEMAS
            if (s.get("function", {}).get("name") or s.get("name", "")) in allowed_tools
        ]

        accumulated_output: list[str] = []
        max_turns = 5
        turn_messages = list(messages)

        for turn in range(max_turns):
            try:
                raw = await self._call_llm_raw(url, model, headers, turn_messages, tool_schemas)
            except Exception as exc:
                logger.warning("[MultiAgent] LLM failed turn %d: %s", turn, exc)
                break

            if not raw:
                break

            content = ""
            tool_calls = []

            if isinstance(raw, dict):
                choices = raw.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    content = msg.get("content") or ""
                    tool_calls = msg.get("tool_calls") or []

            if isinstance(raw, str):
                content = raw

            if not tool_calls:
                if content:
                    accumulated_output.append(content)
                break

            assistant_msg: dict = {"role": "assistant", "content": content or None}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            turn_messages.append(assistant_msg)

            for tc in tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                try:
                    tool_args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    tool_args = {}

                tool_content = self._format_tool_content(tool_name, tool_args)

                logger.info("[MultiAgent] tool: %s args=%.80s", tool_name, str(tool_args)[:80])

                try:
                    block = ToolBlock(tool_type=tool_name, content=tool_content)
                    desc, result = await execute_tool_block(
                        block,
                        session_id=self.session_id,
                        owner=self.session_id,
                    )
                    tool_output = json.dumps(result) if isinstance(result, dict) else str(result)
                    accumulated_output.append(f"[{tool_name}] {desc}")
                    logger.info("[MultiAgent] tool ok: %s → %.80s", tool_name, desc)
                except Exception as tool_exc:
                    tool_output = f"Erreur: {tool_exc}"
                    accumulated_output.append(f"[{tool_name}] ERREUR")
                    logger.warning("[MultiAgent] tool fail: %s → %s", tool_name, tool_exc)

                turn_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{turn}_{tool_name}"),
                        "content": tool_output,
                    }
                )

        return "\n".join(accumulated_output) if accumulated_output else "[Aucune réponse]"

    @staticmethod
    def _format_tool_content(tool_name: str, args: dict) -> str:
        """Formate les arguments selon le parser attendu par tool_execution."""
        if tool_name == "write_file":
            return f"{args.get('path', '')}\n{args.get('content', '')}"
        if tool_name == "bash":
            return args.get("command", "")
        if tool_name == "python":
            return args.get("code", "")
        if tool_name in ("web_search", "web_fetch"):
            return args.get("query") or args.get("url", "")
        if tool_name in ("read_file", "grep", "glob", "ls"):
            return args.get("path") or args.get("pattern") or args.get("query") or ""
        return json.dumps(args)

    async def _call_llm_raw(self, url: str, model: str, headers: dict, messages: list, tools: list) -> dict | None:
        """Appel LLM brut avec outils."""
        import httpx

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 4096,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={**headers, "Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                logger.warning("[MultiAgent] LLM %d: %.200s", resp.status_code, resp.text[:200])
                return None
            return resp.json()

    def _load_agent_prompt(self, agent_name: str) -> str | None:
        try:
            from pathlib import Path

            agents_dir = Path(__file__).parent.parent.parent / ".opencode" / "agents"
            md_file = agents_dir / f"{agent_name}.md"
            if md_file.exists():
                from src.orchestrator.spec import parse_agent_spec

                spec = parse_agent_spec(md_file)
                return spec.prompt or spec.description
        except Exception:
            pass
        return None

    def _summarize_phase(self, report: PhaseReport) -> str:
        parts = []
        for a in report.agents:
            s = "✅" if a.success else "❌"
            parts.append(f"{s} {a.agent} ({a.model}): {a.output[:200]}")
        return "\n".join(parts)

    async def _synthesize(self, report: WorkflowReport) -> str:
        parts = [f"# {self.objective}\n"]
        for pr in report.phases:
            parts.append(f"\n## {pr.phase}")
            parts.append(pr.summary)
        return "\n".join(parts)
