# Plan d'Actions Restantes — Backlog Unique Priorisé

> **Dernière mise à jour :** 2026-08-05 | **Score baseline :** voir le **score mesuré unique** dans `04-OBJECTIFS-COUVERTURE.md` | **Cible :** 100%

---

## 1. Baseline Actuelle

| Axe                        | Score | Cible |
|----------------------------|-------|-------|
| AXE 1 — Orchestration     | 90%   | 95%   |
| AXE 2 — Modularité        | 90%   | 95%   |
| AXE 3 — Routing           | 85%   | 90%   |
| AXE 4 — Trinité           | 90%   | 95%   |
| AXE 5 — Sandbox           | 80%   | 85%   |
| AXE 6 — Gouvernance       | 65%   | 90%   |
| AXE 7 — Apprentissage     | 70%   | 80%   |
| AXE 8 — UI Cockpit        | 95%   | 100%  |
| **GLOBAL**                | **83%** | **100%** |

---

## 2. Bloquants Résolus

| # | Bloquant | Résolution | Date |
|---|----------|-----------|------|
| — | *Aucun bloquant résolu à ce stade* | — | — |

---

## 3. Actions Restantes Priorisées

### P0 — Blocage immédiat (score cible après P0 : 83% → 91%)

| # | Action | Description | Effort | Impact | Dépendances |
|---|--------|-------------|--------|--------|-------------|
| P0.1 | **CBM + Graphify registry** | `docker pull ghcr.io/superpowers-sh/codebase-memory-mcp` → `denied`. Solution : Docker login avec token GitHub (read:packages) OU build from source OU MCP stdio. | 10 min | +3% | Compte GitHub + token |
| P0.2 | **Obsidian MCP — Second Brain** | Kill-switch OFF, pas de vault configuré. Activer `ODYSSEUS_OBSIDIAN_MCP=on` + pointer `OBSIDIAN_VAULT_PATH`. | 5 min | +2% | Vault Obsidian existant |
| P0.3 | **Goal-Ancestry Live** | Tables SQL existent mais pas de création live. Injecter `_create_goal_ancestry()` dans `src/opencode_engine.py:231` après la boucle des phases. | 15 min | +3% | SQLAlchemy SessionLocal |

### P1 — Haute priorité (score cible après P1 : 91% → 96%)

| # | Action | Description | Effort | Impact | Dépendances |
|---|--------|-------------|--------|--------|-------------|
| P1.1 | **Heartbeat Scheduling** | Plugin `@agentos/sfd-heartbeat`. Hook `session.idle` → planifier prochaine exécution via APScheduler. | 1 h | +3% | APScheduler (déjà installé) |
| P1.2 | **npm Packages Publish** | Publier les 9 packages `@agentos/sfd-*` sur npm (`--access public`). Alternative immédiate : `npm link` local. | 10 min | +2% | Compte npmjs.com |

### P2 — Priorité normale (score cible après P2 : 96% → 98%)

| # | Action | Description | Effort | Impact | Dépendances |
|---|--------|-------------|--------|--------|-------------|
| P2.1 | **VPS Deployment** | `docker compose --profile production up -d` sur Ubuntu 22.04+. Traefik + Let's Encrypt configurés automatiquement. | 1 h | +2% | `.env` avec `OPENCODE_API_KEY`, VPS provisionné |

### P3 — Optimisation (score cible après P3 : 98% → 100%)

| # | Action | Description | Effort | Impact | Dépendances |
|---|--------|-------------|--------|--------|-------------|
| P3.1 | **Dashboard Trinité unifié** | UI cockpit custom regroupant les 3 vues (orchestration, gouvernance, apprentissage). | 4 h | +1% | P1.1 (heartbeat) |
| P3.2 | **Auto-skills generation** | Intégration acontex pour génération automatique de skills. | 3 h | +0.5% | — |
| P3.3 | **Per-agent model routing live** | Routage dynamique des modèles par agent via OpenCode natif. | 2 h | +0.5% | — |
| P3.4 | **gVisor runtime activation** | Activation du sandbox gVisor pour isolation renforcée. | 2 h | +0% | Kernel Linux 4.x+ |

---

## 4. Score Projeté par Palier

| Palier | Actions | Score projeté | Delta |
|--------|---------|---------------|-------|
| Baseline | — | 83% | — |
| Après P0 | CBM+Graphify, Obsidian, Goal-Ancestry | 91% | +8% |
| Après P1 | Heartbeat, npm Publish | 96% | +5% |
| Après P2 | VPS Deploy | 98% | +2% |
| Après P3 | Dashboard, Auto-skills, Model routing, gVisor | 100% | +2% |

---

## 5. Tableau de Bord

| # | Action | Statut | Priorité | Effort | Impact |
|---|--------|--------|----------|--------|--------|
| P0.1 | CBM + Graphify registry | `todo` | P0 | 10 min | +3% |
| P0.2 | Obsidian MCP | `todo` | P0 | 5 min | +2% |
| P0.3 | Goal-Ancestry Live | `todo` | P0 | 15 min | +3% |
| P1.1 | Heartbeat Scheduling | `todo` | P1 | 1 h | +3% |
| P1.2 | npm Packages Publish | `todo` | P1 | 10 min | +2% |
| P2.1 | VPS Deployment | `todo` | P2 | 1 h | +2% |
| P3.1 | Dashboard Trinité | `todo` | P3 | 4 h | +1% |
| P3.2 | Auto-skills generation | `todo` | P3 | 3 h | +0.5% |
| P3.3 | Per-agent model routing | `todo` | P3 | 2 h | +0.5% |
| P3.4 | gVisor runtime activation | `todo` | P3 | 2 h | +0% |

---

## 6. Risques

| Risque | Probabilité | Impact | Mitigation |
|--------|------------|--------|------------|
| Token GitHub expiré/absent pour CBM | Moyenne | Bloque P0.1 | Build from source (solution B) ou MCP stdio (solution C) |
| Vault Obsidian inexistant | Faible | Bloque P0.2 | Créer un vault minimal avec `obsidian_mcp_init` |
| Compte npm non créé | Moyenne | Bloque P1.2 | `npm link` local en attendant |
| VPS non provisionné | Moyenne | Bloque P2.1 | Déploiement local Docker comme fallback |
| APScheduler conflit de version | Faible | Ralentit P1.1 | Déjà dans les dépendances, vérifié |
| gVisor non compatible | Faible | Bloque P3.4 | Item non critique, skip possible |
