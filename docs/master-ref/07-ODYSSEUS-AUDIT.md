# Audit Odysseus — Pertinence pour notre Vision

> ⚠️ **RÉVISÉ 2026-09-25 — réalité vérifiée.** La cible « 55 → 15 routes / ~50 fichiers » **n'a pas été atteinte** (**63 routes, 1 071 `.py` actifs**). Les mentions ci-dessous sont des cibles ; état réel : `../traceability/00-CODE-INVENTORY.md`.


> **Question :** Odysseus est-il encore le bon socle UI, ou faut-il le remplacer ?

---

## Ce qu'Odysseus apporte (171 fichiers Python)

| Composant | Valeur | Lourd à adapter ? |
|-----------|--------|-------------------|
| **FastAPI + SSE** | Streaming live, 55 routes | 🟢 Léger — socle parfait |
| **Chat UI (static/)** | 162 fichiers JS, SPA vanilla | 🟡 Moyen — complexe mais fonctionnel |
| **Cockpit** | Phase bar, health, drift | 🟢 On l'a déjà adapté |
| **Settings dashboard** | Kill-switches, config | 🟢 Réutilisable |
| **Email/Calendar** | IMAP/SMTP, CalDAV | 🟢 Indépendant, gardable |
| **Cookbook** | Gestion modèles, VRAM | 🟡 Spécifique, lourd |
| **Tool implementations** | BASH, WRITE_FILE, WEB_SEARCH | 🟢 Essentiel, garder |
| **MCP Manager** | 6 serveurs, 3 transports | 🟢 Essentiel, garder |
| **Docker Compose** | 10 services, profils | 🟢 Essentiel, garder |
| **agent_loop.py** | 3992 lignes, cœur du LLM | 🔴 Trop lourd — à remplacer par OpenCode Engine |
| **llm_core.py** | 2520 lignes, streaming HTTP | 🟡 Remplaçable par ZenRouter natif |
| **zen_router.py** | 354 lignes, routing | 🟢 Garder (déjà intégré à OpenCode) |
| **50+ routes** | Tasks, Notes, Gallery, Cookbook... | 🟡 70% inutiles pour notre vision agent |

---

## Verdict : GARDER, mais ÉLAGUER

| Action | Composants |
|--------|-----------|
| **GARDER** | FastAPI, SSE, Chat UI, Cockpit, Kill-switches, Docker, MCP Manager, Tool implementations, Email/Calendar, ZenRouter |
| **SUPPRIMER** | agent_loop.py (→ OpenCode Engine), llm_core.py (→ ZenRouter natif), Cookbook (trop spécifique), Gallery, Deep Research (déjà dans OpenCode) |
| **RÉDUIRE** | 55 routes → 15 routes essentielles (cible **non atteinte** : 63 routes) |

---

## Alternative : UI Légère from scratch

| Approche | Avantages | Inconvénients |
|----------|-----------|---------------|
| **Garder Odysseus élagué** | 0 réécriture UI, FastAPI mature, Docker prêt | cible ~50 fichiers (réel : 1 071 `.py` actifs), héritage complexe |
| **UI légère (FastAPI + HTMX)** | Propre, 100% adapté à notre vision | 2-3 semaines de rebuild, perd Email/Calendar |
| **OpenCode Web UI native** | Zéro code UI, 100% natif OpenCode | Fonctionnalités limitées (pas de cockpit custom) |

---

## Recommandation

**Garder Odysseus élagué.** On supprime agent_loop.py, llm_core.py, Cookbook, Gallery, routes inutiles. On garde le strict nécessaire : FastAPI, Chat UI, Cockpit, Docker, MCP. On branche OpenCode Engine comme moteur unique.

```
Odysseus ÉLAGUÉ (cible ~50 fichiers ; réel 1 071 actifs)
├── app.py              FastAPI (allégé)
├── routes/
│   ├── chat_routes.py  → OpenCode Engine
│   ├── health.py       → /api/health
│   ├── cockpit.py      → SSE events
│   └── settings.py     → kill-switches
├── src/
│   ├── opencode_engine.py  → moteur principal
│   ├── event_bus.py        → event bus central
│   ├── zen_router.py       → routing (gardé)
│   ├── mcp_manager.py      → MCP (gardé)
│   └── tool_implementations.py → outils (gardé)
├── static/             UI (allégée)
├── docker-compose.yml  services
└── .opencode/          agents, skills, tools, config
```
