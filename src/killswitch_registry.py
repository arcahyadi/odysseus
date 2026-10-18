"""Read-only registry of odysseus kill-switches.

Pure module (no file I/O, no mutation of os.environ). Each descriptor is
curated and cites the exact code location where the switch is read, so the
dashboard stays honest and verifiable. read_states() resolves the live
os.environ value for each switch; a switch whose env var is unset reports
is_default=True and falls back to the code default.
"""

from __future__ import annotations

import os
from typing import Any

_TRUTHY = ("1", "true", "yes", "on")


def _truthy(value: str | None) -> bool:
    return str(value).strip().lower() in _TRUTHY if value is not None else False


# Curated set — grounded in code (rg 'os\.(environ\.get|getenv)\("ODYSSEUS_')
# plus the agent/channel gates. Config params (paths, ids, models) are excluded.
_SWITCHES: list[dict[str, Any]] = [    {
        "name": "Live orchestration",
        "env_var": "ODYSSEUS_LIVE_ORCHESTRATION",
        "default": "off",
        "category": "Orchestration",
        "timing": "runtime",
        "desc": "CanonicalLoop 7 phases.",
        "source": "archive/legacy/agent_loop.py:2933",
    },
    {
        "name": "Phase tracker",
        "env_var": "ODYSSEUS_PHASE_TRACKER",
        "default": "on",
        "category": "Orchestration",
        "timing": "runtime",
        "desc": "Infere la phase par round et la pousse au ToolRegistry.",
        "source": "src/orchestrator/phase_tracker.py:23",
    },
    {
        "name": "Model router",
        "env_var": "ODYSSEUS_MODEL_ROUTER",
        "default": "on",
        "category": "Orchestration",
        "timing": "runtime",
        "desc": "Routing advisory log-only (n'ecrase pas le modele user).",
        "source": "src/orchestrator/router_advice.py:42",
    },
    {
        "name": "Destructive gate",
        "env_var": "ODYSSEUS_DESTRUCTIVE_GATE",
        "default": "on",
        "category": "Orchestration",
        "timing": "runtime",
        "desc": "Garde-fou operations destructrices (ON par defaut).",
        "source": "src/orchestrator/gate.py:26",
    },
    {
        "name": "Autoeval",
        "env_var": "ODYSSEUS_AUTOEVAL",
        "default": "on",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "Decision keep/revert post-build.",
        "source": "src/orchestrator/autoeval.py:45",
    },
    {
        "name": "Autoeval: exécution destructrice",
        "env_var": "ODYSSEUS_AUTOEVAL_ALLOW_RESET",
        "default": "off",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "AUTOEVAL peut DECIDER un revert ; ce switch autorise son "
                "EXECUTION (git reset --hard). OFF par defaut : la decision "
                "est tracee, l'action jamais jouee.",
        "source": "src/orchestrator/autoeval.py:62",
    },
    {
        "name": "Autoevolve",
        "env_var": "ODYSSEUS_AUTOEVOLVE",
        "default": "on",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "Recherche d'amelioration apres drift HIGH + revert.",
        "source": "src/orchestrator/autoevolve.py:18",
    },
    {
        "name": "CodeBurn",
        "env_var": "ODYSSEUS_CODEBURN",
        "default": "off",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "Rapport one-shot rate / waste / cout.",
        "source": "src/orchestrator/codeburn_runner.py:26",
    },
    {
        "name": "LangFuse",
        "env_var": "ODYSSEUS_LANGFUSE",
        "default": "off",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "LLM tracing & observability dashboard (self-hosted).",
        "source": "services/observability/langfuse_tracer.py:38",
    },
    {
        "name": "Governance ancestry",
        "env_var": "ODYSSEUS_GOVERNANCE_ANCESTRY",
        "default": "off",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "Ecrit GoalTask avec ancestry mission->goal->project->task.",
        "source": "src/orchestrator/ancestry_tracker.py:26",
    },
    {
        "name": "LangGraph loop",
        "env_var": "ODYSSEUS_LANGGRAPH",
        "default": "off",
        "category": "Orchestration",
        "timing": "runtime",
        "desc": "StateGraph 7-nœuds (remplace stream_agent_loop).",
        "source": "src/orchestrator/langgraph_loop.py:42",
    },
    {
        "name": "LangGraph interrupt",
        "env_var": "ODYSSEUS_LANGGRAPH_INTERRUPT",
        "default": "on",
        "category": "Orchestration",
        "timing": "runtime",
        "desc": "Interrupt before BUILD when risk==DESTRUCTIVE.",
        "source": "src/orchestrator/langgraph_loop.py:805",
    },
    {
        "name": "Checkpoint",
        "env_var": "ODYSSEUS_CHECKPOINT",
        "default": "on",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "Persiste un checkpoint post-round dans Obsidian.",
        "source": "src/orchestrator/checkpoint_tracker.py:39",
    },
    {
        "name": "Unified tokens",
        "env_var": "ODYSSEUS_UNIFIED_TOKENS",
        "default": "on",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "Comptage tokens unifie avec run_id de correlation.",
        "source": "src/trace_writer.py:146",
    },
    {
        "name": "RRF fusion",
        "env_var": "ODYSSEUS_RRF_FUSION",
        "default": "off",
        "category": "RAG",
        "timing": "runtime",
        "desc": "Fusion vecteur+BM25 par Reciprocal Rank Fusion.",
        "source": "src/rag_vector.py:86",
    },
    {
        "name": "Docling",
        "env_var": "ODYSSEUS_DOCLING",
        "default": "off",
        "category": "Document Processing",
        "timing": "runtime",
        "desc": "PDF extraction via Docling (tables, layout, reading order).",
        "source": "src/docling_runtime.py:30",
    },
    {
        "name": "DeepEval",
        "env_var": "ODYSSEUS_DEEPEVAL",
        "default": "off",
        "category": "Quality",
        "timing": "runtime",
        "wired": False,
        "desc": "AUCUN LECTEUR dans le code : declarer ce switch est sans effet. LLM quality evaluation (faithfulness, relevancy, hallucination, bias, toxicity).",
        "source": "(aucun lecteur dans le code)",
    },
    {
        "name": "Tree-sitter",
        "env_var": "ODYSSEUS_TREESITTER",
        "default": "off",
        "category": "Code Parsing",
        "timing": "runtime",
        "desc": "Incremental syntax parsing (AST, symbols, call sites).",
        "source": "src/agent_tools/filesystem_tools.py:16",
    },
    {
        "name": "Disable MCP",
        "env_var": "ODYSSEUS_DISABLE_MCP",
        "default": "off",
        "category": "MCP/Services",
        "timing": "startup",
        "desc": "Coupe tous les serveurs MCP built-in (lu au boot).",
        "source": "src/builtin_mcp.py:90",
    },
    {
        "name": "Obsidian MCP",
        "env_var": "ODYSSEUS_OBSIDIAN_MCP",
        "default": "off",
        "category": "MCP/Services",
        "timing": "runtime",
        "desc": "Active le serveur MCP Obsidian.",
        "source": "src/builtin_mcp.py:99",
    },
    {
        "name": "Graphify",
        "env_var": "ODYSSEUS_GRAPHIFY",
        "default": "off",
        "category": "MCP/Services",
        "timing": "runtime",
        "desc": "Active le serveur MCP Graphify.",
        "source": "src/builtin_mcp.py:108",
    },
    {
        "name": "CBM (Codebase Memory)",
        "env_var": "ODYSSEUS_CBM",
        "default": "off",
        "category": "MCP/Services",
        "timing": "runtime",
        "desc": "Active le client CBM pour le graphe semantique de code.",
        "source": "src/cbm_client.py:24",
    },
    {
        "name": "Serena MCP",
        "env_var": "ODYSSEUS_SERENA_MCP",
        "default": "off",
        "category": "MCP/Services",
        "timing": "runtime",
        "desc": "Active le client Serena MCP (find_references, goto_definition, etc.).",
        "source": "src/serena_client.py:25",
    },
    {
        "name": "AgentSeal",
        "env_var": "ODYSSEUS_AGENTSEAL",
        "default": "off",
        "category": "MCP/Services",
        "timing": "runtime",
        "desc": "Active le scanner d'injection AgentSeal (prompts + outputs).",
        "source": "src/agentseal_runner.py:82",
    },
    {
        "name": "Supabase",
        "env_var": "ODYSSEUS_SUPABASE",
        "default": "off",
        "category": "MCP/Services",
        "timing": "startup",
        "wired": False,
        "desc": "AUCUN LECTEUR dans le code : declarer ce switch est sans effet. Active l'integration Supabase (backend-as-a-service).",
        "source": "(aucun lecteur dans le code)",
    },
    {
        "name": "Vaultwarden",
        "env_var": "ODYSSEUS_VAULTWARDEN",
        "default": "off",
        "category": "MCP/Services",
        "timing": "runtime",
        "wired": False,
        "desc": "AUCUN LECTEUR dans le code : declarer ce switch est sans effet. Active l'integration Vaultwarden (password manager).",
        "source": "(aucun lecteur dans le code)",
    },
    {
        "name": "Playwright MCP",
        "env_var": "ODYSSEUS_PLAYWRIGHT",
        "default": "off",
        "category": "MCP/Services",
        "timing": "runtime",
        "wired": False,
        "desc": "AUCUN LECTEUR dans le code : declarer ce switch est sans effet. Active le serveur MCP Playwright pour le browsing headless.",
        "source": "(aucun lecteur dans le code)",
    },
    {
        "name": "Browser Harness",
        "env_var": "ODYSSEUS_BROWSER_HARNESS",
        "default": "off",
        "category": "MCP/Services",
        "timing": "runtime",
        "wired": False,
        "desc": "AUCUN LECTEUR dans le code : declarer ce switch est sans effet. Active le harness de navigateur pour les tests E2E.",
        "source": "(aucun lecteur dans le code)",
    },
    {
        "name": "Zen from endpoint",
        "env_var": "ODYSSEUS_ZEN_FROM_ENDPOINT",
        "default": "off",
        "category": "MCP/Services",
        "timing": "runtime",
        "desc": (
            "Route Zen via un endpoint enregistre. LECTEUR REEL : "
            "zen_router.py — teste avec `== \"1\"` quand OPENCODE_API_KEY est absente. "
            "Declare `wired=False` jusqu'a l'item 2 du Sprint 4, sur la foi du verificateur "
            "de `tests/test_killswitch_registry.py` : or ce verificateur ne voyait pas les "
            "lectures SANS defaut litteral, que celle-ci est. Le drapeau avait donc pourri "
            "sans bruit. Corrige ici en meme temps que le verificateur, sinon le mensonge "
            "serait reintroduit au prochain nettoyage."
        ),
        "source": "src/zen_router.py:130",
    },
    {
        "name": "n8n integration",
        "env_var": "ODYSSEUS_N8N",
        "default": "off",
        "category": "MCP/Services",
        "timing": "runtime",
        "desc": "Active la routing n8n pour trigger de workflows.",
        "source": "routes/n8n_routes.py:27",
    },
    {
        "name": "In-process Discord",
        "env_var": "ODYSSEUS_INPROCESS_DISCORD",
        "default": "off",
        "category": "Channels",
        "timing": "startup",
        "wired": False,
        "desc": "AUCUN LECTEUR dans le code : declarer ce switch est sans effet. Bootstrap du bot Discord in-process.",
        "source": "(aucun lecteur dans le code)",
    },
    {
        "name": "In-process Telegram",
        "env_var": "ODYSSEUS_INPROCESS_TELEGRAM",
        "default": "off",
        "category": "Channels",
        "timing": "startup",
        "wired": False,
        "desc": "AUCUN LECTEUR dans le code : declarer ce switch est sans effet. Bootstrap du bot Telegram in-process.",
        "source": "(aucun lecteur dans le code)",
    },
    {
        "name": "Channel agent reply",
        "env_var": "ODYSSEUS_CHANNEL_AGENT_REPLY",
        "default": "off",
        "category": "Channels",
        "timing": "runtime",
        "wired": False,
        "desc": "AUCUN LECTEUR dans le code : declarer ce switch est sans effet. Reponse auto de l'agent sur les channels.",
        "source": "(aucun lecteur dans le code)",
    },
    {
        "name": "Agent catalog",
        "env_var": "ODYSSEUS_AGENT_CATALOG",
        "default": "off",
        "category": "Agents",
        "timing": "startup",
        "desc": "Charge le catalogue d'agents .opencode au boot.",
        "source": "core/startup.py:278",
    },
    {
        "name": "Progressive disclosure",
        "env_var": "ODYSSEUS_PROGRESSIVE_DISCLOSURE",
        "default": "on",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "P5: Restreint les outils visibles par phase+risque.",
        "source": "src/progressive_disclosure.py:27",
    },
    {
        "name": "Memory impact verification",
        "env_var": "ODYSSEUS_MEMORY_IMPACT",
        "default": "on",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "P19: Ne stocke que les faits qui changent les reponses.",
        "source": "src/memory_impact.py:28",
    },
    {
        "name": "Output router",
        "env_var": "ODYSSEUS_OUTPUT_ROUTER",
        "default": "on",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "P22: Routage de la sortie (HTML/SVG inline, Kroki).",
        "source": "src/output_router.py:30",
    },
    {
        "name": "Preferences",
        "env_var": "ODYSSEUS_PREFERENCES",
        "default": "on",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "P12: Preferences utilisateur persistees.",
        "source": "src/preferences.py:41",
    },
    {
        "name": "Data classification",
        "env_var": "ODYSSEUS_DATA_CLASSIFICATION",
        "default": "on",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "P21: Classification 5 niveaux de retention.",
        "source": "src/data_classification.py:28",
    },
    {
        "name": "Content security",
        "env_var": "ODYSSEUS_CONTENT_SECURITY",
        "default": "on",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "P20: Injection guard + filtre de sortie.",
        "source": "src/content_security.py:24",
    },
    {
        "name": "Durable execution",
        "env_var": "ODYSSEUS_DURABLE_EXECUTION",
        "default": "on",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "P14: Execution durable (Custom SQLite).",
        "source": "src/durable_execution.py:32",
    },
    {
        "name": "Provenance memory",
        "env_var": "ODYSSEUS_PROVENANCE_MEMORY",
        "default": "on",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "P16: Memoire taguee [stated]/[observed]/[inferred].",
        "source": "src/provenance_memory.py:40",
    },
]

# 12 phase/explicit agent switches (agent_dispatcher.py). All default off,
# runtime-read via AgentDispatcher.dispatch_for_phase.
_AGENT_SWITCHES = [
    ("Agent: constitution", "ODYSSEUS_AGENT_CONSTITUTION"),
    ("Agent: gsd-planner", "ODYSSEUS_AGENT_PLANNER"),
    ("Agent: gsd-researcher", "ODYSSEUS_AGENT_RESEARCHER"),
    ("Agent: gsd-executor", "ODYSSEUS_AGENT_EXECUTOR"),
    ("Agent: gsd-debugger", "ODYSSEUS_AGENT_DEBUGGER"),
    ("Agent: debate-5-personas", "ODYSSEUS_AGENT_DEBATE"),
    ("Agent: security-audit", "ODYSSEUS_AGENT_SECURITY"),
    ("Agent: gsd-verifier", "ODYSSEUS_AGENT_VERIFIER"),
    ("Agent: edge-case-gen", "ODYSSEUS_AGENT_EDGECASE"),
    ("Agent: gsd-roadmapper", "ODYSSEUS_AGENT_ROADMAPPER"),
    ("Agent: design-extract", "ODYSSEUS_AGENT_DESIGN_EXTRACT"),
    ("Agent: open-design", "ODYSSEUS_AGENT_OPEN_DESIGN"),
]
_SWITCHES.extend(
    {
        "name": label,
        "env_var": var,
        "default": "off",
        "category": "Agents",
        "timing": "runtime",
        "desc": "Dispatch auto de l'agent par phase canonique.",
        "source": "src/orchestrator/agent_dispatcher.py",
    }
    for label, var in _AGENT_SWITCHES
)

# ─── Capacités lues par le code, absentes du registre (Sprint 4 item 2) ───────
#
# Ces onze interrupteurs étaient lus par le code de production et absents du
# registre : le tableau ne pouvait donc pas répondre à sa seule question, « qu'est-ce
# qui est actif ? ». Douze au départ ; la douzième, `ODYSSEUS_DURABLE_EXEC`, a
# été supprimée par l'item 1 (câblage mort dans `launch_fast.py`) et n'a donc
# plus de lecteur — l'inscrire aurait créé exactement le mensonge que ce
# registre existe pour éviter.
#
# **`source` est mesuré, pas supposé.** L'ordre de préférence de lecture exclut
# `scripts/` et `tools/` : un script de fumée n'est pas le lecteur d'un service.
#
# **`ODYSSEUS_OPA` est un cas à part, et le v8 a tranché « couper par défaut,
# `wired=False` ». J'ai appliqué la moitié qui est juste et refusé l'autre, pour
# une raison qui tient : `wired` signifie « un lecteur existe », et
# `opa_client.py:23` en est un. Écrire `wired=False` afficherait « ce switch
# n'est pas réel » alors que la lecture est réelle et que c'est l'INTEGRATION qui
# manque — un mensonge dans l'autre sens, ce qui n'est pas mieux. Donc
# `wired=True`, `default=off`, et la raison est dans la description, qui est le
# champ fait pour la dire.
#
# Les défauts ci-dessous sont mesurés sur le code, pas déduits du nom :
#   OPA      `opa_client.py:23`  — couplé par défaut, coupé par la décision v8
#   OTEL     `otel_setup.py:39`  — le seul de ces onze qui soit `on`
#   les 9 autres : `off`
_INTEGRATION_SWITCHES = [
    {
        "name": "Politique de securite (OPA)",
        "env_var": "ODYSSEUS_OPA",
        "default": "off",
        "category": "MCP/Services",
        "timing": "runtime",
        "desc": (
            "Moteur de politique de securite. Implementation fail-closed correcte "
            "(timeout et erreur de connexion refusent), MAIS aucun module de production "
            "n'importe services.security.opa_client : la politique n'est donc jamais "
            "interrogee. Coupe par defaut (decision Sprint 4) plutot que laisse apparent "
            "comme actif. Brancher le module est un chantier a part."
        ),
        "source": "services/security/opa_client.py:23",
    },
    {
        "name": "Telemetrie OpenTelemetry",
        "env_var": "ODYSSEUS_OTEL",
        "default": "on",
        "category": "Quality",
        "timing": "runtime",
        "desc": "Telemetrie OTel. Seule de ces entrees activee par defaut, et invisible jusqu'ici du tableau.",
        "source": "services/observability/otel_setup.py:39",
    },
    {
        "name": "Push externe (Apprise)",
        "env_var": "ODYSSEUS_APPRISE",
        "default": "off",
        "category": "Channels",
        "timing": "runtime",
        "desc": "Push multi-canal externe. Eteint par defaut : coherent avec UC-09, dont l'alarme passe par la piste d'audit.",
        "source": "src/channel_gateway.py:78",
    },
    {
        "name": "Recherche Meilisearch",
        "env_var": "ODYSSEUS_MEILISEARCH",
        "default": "off",
        "category": "RAG",
        "timing": "runtime",
        "desc": "Fournisseur de recherche.",
        "source": "services/search/meilisearch_client.py:21",
    },
    {
        "name": "Moteur de planification",
        "env_var": "ODYSSEUS_PLANNING_ENGINE",
        "default": "off",
        "category": "Orchestration",
        "timing": "runtime",
        "desc": "Creation et suivi de plans de projet (M6.7).",
        "source": "src/planning_engine.py:27",
    },
    {
        "name": "Ordonnanceur Prefect",
        "env_var": "ODYSSEUS_PREFECT",
        "default": "off",
        "category": "MCP/Services",
        "timing": "runtime",
        "desc": "Ordonnanceur de taches distribue.",
        "source": "services/pipelines/maintenance_pipeline.py:19",
    },
    {
        "name": "Base vectorielle Qdrant",
        "env_var": "ODYSSEUS_QDRANT",
        "default": "off",
        "category": "RAG",
        "timing": "runtime",
        "desc": "Base vectorielle (memoire et RAG).",
        "source": "src/memory_vector.py:29",
    },
    {
        "name": "Memoire Letta",
        "env_var": "ODYSSEUS_LETTA",
        "default": "off",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "Fournisseur de memoire Letta. Defaut mesure : _env_truthy sur une variable absente donne faux.",
        "source": "services/memory/letta_provider.py:54",
    },
    {
        "name": "Memoire Mem0",
        "env_var": "ODYSSEUS_MEM0",
        "default": "off",
        "category": "Governance/Memory",
        "timing": "runtime",
        "desc": "Fournisseur de memoire Mem0. Defaut mesure : la lecture est INVERSEE (not _env_falsy), donc off si absente, on des que la variable est posee.",
        "source": "services/memory/mem0_provider.py:54",
    },
    {
        "name": "Dispatch multi-agent",
        "env_var": "ODYSSEUS_MULTI_AGENT",
        "default": "off",
        "category": "Orchestration",
        "timing": "runtime",
        "desc": "Dispatch multi-agent. UC-10 est une escalade gelee : inscrit ici pour VISIBILITE, defaut inchange. Rendre visible n'est pas activer.",
        "source": "archive/legacy/agent_loop.py:3025",
    },
    {
        "name": "Execution distante de scripts (SSH)",
        "env_var": "ODYSSEUS_REMOTE_SSH",
        "default": "off",
        "category": "MCP/Services",
        "timing": "runtime",
        "desc": (
            "Execution de code sur une AUTRE machine via ssh. Capacite sans "
            "interrupteur jusqu'au Sprint 4 item 5 ; fermee par defaut. Mesure "
            "prealable (v9) : aucun appelant ne passe `host`, et le seul point "
            "d'entree de l'action est la route de taches, dont les actions "
            "d'execution sont admin-only — donc aucun chemin de code reel n'en "
            "profitait. Le defaut est `off` et NON « refleter le comportement "
            "actuel » : une capacite d'execution a distance n'a pas de "
            "comportement a preserver, elle a une exposition a fermer. La "
            "branche n'est pas supprimee, elle est une porte."
        ),
        "source": "src/builtin_actions.py:381",
    },
    {
        "name": "Execution distante de scripts (cible SSH)",
        "env_var": "ODYSSEUS_SCRIPT_HOST",
        "default": "off",
        "category": "MCP/Services",
        "timing": "runtime",
        "desc": (
            "Cible SSH pour l'execution de scripts distants. Lue par "
            "builtin_actions.py:394 comme valeur par défaut de `host`. "
            "Capacite sans interrupteur jusqu'a maintenant : la variable etait "
            "posee par le lanceur mais non governee. Fermee par defaut. "
            "Brancher un appelant qui passe `host` est un chantier a part."
        ),
        "source": "src/builtin_actions.py:394",
    },
    {
        "name": "Decouverte dynamique d'outils",
        "env_var": "ODYSSEUS_TOOL_DISCOVERY",
        "default": "off",
        "category": "MCP/Services",
        "timing": "runtime",
        "desc": "Decouverte d'outils (INT-7). Le code lit bien l'interrupteur, mais `tool_search` n'a aucune occurrence : rien a decouvrir pour l'instant.",
        "source": "src/content_security.py:112",
    },
]
_SWITCHES.extend(_INTEGRATION_SWITCHES)

_CATEGORY_ORDER = [
    "Orchestration",
    "Governance/Memory",
    "RAG",
    "Code Parsing",
    "MCP/Services",
    "Document Processing",
    "Quality",
    "Channels",
    "Agents",
]


def categories() -> list[str]:
    """Stable display order of switch categories."""
    return list(_CATEGORY_ORDER)


def read_states() -> list[dict[str, Any]]:
    """Return each descriptor enriched with live env state.

    Adds raw (env value or None), is_default (True if unset), and effective
    (resolved bool). Best-effort per descriptor: never raises.

    `effective` answers "is this switch on?", NOT "is this switch real?".
    A descriptor flagged ``wired=False`` has no reader anywhere in the code,
    so it can report effective=True while changing nothing at all. The
    dashboard must read `wired` too — an unreachable switch presented as
    active is exactly the kind of lie this registry exists to prevent.
    """
    rows: list[dict[str, Any]] = []
    for d in _SWITCHES:
        raw = os.environ.get(d["env_var"])
        is_default = raw is None
        effective = _truthy(d["default"]) if is_default else _truthy(raw)
        rows.append(
            {
                **d,
                "raw": raw,
                "is_default": is_default,
                "effective": effective,
                "wired": d.get("wired", True),
            }
        )
    return rows
