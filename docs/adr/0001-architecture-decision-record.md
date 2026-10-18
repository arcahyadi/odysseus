# ADR-0001 : Odysseus comme couche UI mince FastAPI déléguant à OpenCode Engine

**Statut :** Accepté

**Date :** 2026-07-24

**Décideurs :** Équipe Odysseus AgentOS

---

## Contexte

### Problème initial

L'audit d'Odysseus (juillet 2026 — voir `docs/master-ref/07-ODYSSEUS-AUDIT.md`) a révélé une codebase Python de 171 fichiers (~17 000 lignes) avec un cœur LLM devenu ingérable :

- `agent_loop.py` : 3 992 lignes — le cœur du raisonnement agent, monolithique et couplé à tout
- `llm_core.py` : 2 520 lignes — streaming HTTP, gestion des providers, retries
- `zen_router.py` : 354 lignes — routage intelligent des modèles
- Modules SFD dispersés : `durable_execution/`, `memory_provenance/`, `preferences/`, `visual_output/`, `classification/`, `content_security/`, `tool_discovery/` (~1 950 lignes)

**Symptômes :** Impossible de modifier le comportement agent sans impacter le système entier. Chaque module SFD était couplé à `agent_loop.py`. Les tests unitaires étaient impossibles sans mocker la moitié du système.

### Opportunité identifiée

OpenCode Engine (Node.js) offrait déjà nativement :
- **16 agents** spécialisés (`.opencode/agents/`) avec ZenRouter natif
- **Système de plugins npm** avec hooks (`session.created`, `tool.execute.before/after`)
- **Worktrees** natifs pour l'isolation de projets
- **Compaction** automatique du contexte
- **Permissions** granulaires par agent

La question était : **faut-il remplacer Odysseus entièrement ou le conserver comme couche UI ?**

### Alternatives considérées

| Approche | Avantages | Inconvénients |
|----------|-----------|---------------|
| **A. Réécriture complète** (FastAPI + HTMX from scratch) | Propre, 100% adapté | 2-3 semaines, perd Email/Calendar/MCP Manager |
| **B. OpenCode Web UI native** | Zéro code UI | Fonctionnalités limitées, pas de cockpit custom |
| **C. Odysseus élagué + bridge** | 0 réécriture UI, Docker prêt, 3 jours de travail | Héritage complexe à nettoyer |

---

## Décision

**Nous avons choisi l'option C : conserver Odysseus comme couche UI mince (~50 fichiers Python) et déléguer toute l'intelligence agent à OpenCode Engine via un bridge subprocess.**

### Architecture retenue

```
Odysseus (Python/FastAPI) — couche mince ~50 fichiers
  opencode_bridge.py → subprocess → OpenCode CLI (Node.js)
    stdin: message
    stdout: response + phase events → SSE → cockpit + chat UI
    stderr: logs

OpenCode CLI utilise :
  - ZenRouter (sélection de modèle)
  - 16 agents (.opencode/agents/)
  - 8 serveurs MCP
  - 7 plugins npm (@agentos/sfd-*)
  - 2 skills (.opencode/skills/)
  - 1 custom tool (.opencode/tools/sfd-phase.ts)
  - Worktrees, compaction, permissions natifs
```

### Bridge technique

Le bridge (`src/opencode_bridge.py`) fonctionne en deux modes :
1. **Mode engine isolé** (`AGENTOS_ENGINE_HOST` défini) : route les requêtes vers le conteneur `agentos-engine` (port 7001) via HTTP/SSE
2. **Mode legacy** (`AGENTOS_ENGINE_HOST` vide) : utilise le stream agent interne (développement)

L'engine isolé tourne dans `docker/agentos-engine/` avec son propre Dockerfile et `engine_server.py`.

### Suppressions opérées

| Composant supprimé | Lignes | Remplacé par |
|--------------------|--------|-------------|
| `agent_loop.py` | 3 992 | OpenCode Engine |
| `llm_core.py` | 2 520 | ZenRouter natif |
| `zen_router.py` | 354 | ZenRouter natif |
| 7 modules SFD | ~1 950 | 7 plugins npm `@agentos/sfd-*` |
| Routes inutiles | ~600 | Réduction 55 → 15 routes |
| **Total** | **~12 300** | |

### Composants conservés

- **FastAPI + SSE** : socle parfait pour le streaming live
- **Chat UI** (`static/`, 162 fichiers JS) : SPA vanilla fonctionnelle
- **Cockpit** : barre de phases, health, drift — déjà adapté à OpenCode
- **Settings dashboard** : kill-switches, configuration
- **Email/Calendar** : IMAP/SMTP, CalDAV — indépendants du moteur LLM
- **Docker Compose** : 15 services + profils — infrastructure inchangée
- **MCP Manager** : 6+ serveurs, 3 transports
- **Tool implementations** : BASH, WRITE_FILE, WEB_SEARCH
- **ZenRouter (concept)** : déjà natif dans OpenCode

### 7 plugins npm SFD

| Package | Module SFD | Rôle |
|---------|-----------|------|
| `@agentos/sfd-memory` | Memory Provenance | Mémoire avec tags `[stated]`/`[observed]`/`[inferred]` |
| `@agentos/sfd-durable` | Durable Execution | Reprise après panne, retry, compensation |
| `@agentos/sfd-prefs` | Preferences | Préférences comportementales et contextuelles |
| `@agentos/sfd-visual` | Visual Output | Widgets SVG/HTML interactifs |
| `@agentos/sfd-classify` | Classification | Classification et oubli sécurisé |
| `@agentos/sfd-security` | Content Security | Audit de contenu, prompt injection |
| `@agentos/sfd-discovery` | Tool Discovery | Registre MCP, découverte dynamique |

---

## Conséquences

### Positives

1. **Codebase Python réduite de 72%** : ~17 000 → ~5 000 lignes
2. **Séparation claire des responsabilités** : UI (Odysseus) vs Intelligence (OpenCode)
3. **Agents testables unitairement** : chaque plugin npm est un package indépendant
4. **Mise à jour indépendante** : OpenCode peut évoluer sans toucher à Odysseus
5. **Déploiement isolé** : `agentos-engine` et `agentos-sandbox` dans leur propre réseau Docker
6. **Zéro régression fonctionnelle** : toutes les features UI conservées

### Négatives

1. **Deux runtimes** (Python + Node.js) à maintenir
2. **Latence ajoutée** : bridge subprocess/HTTP ajoute ~50-200ms par requête
3. **Debug inter-process** plus complexe qu'un processus unique
4. **Deux systèmes de logging** à corréler (Python + Node.js)
5. **Dépendance à OpenCode** : si OpenCode change son API, le bridge doit s'adapter

### Risques

1. **Dépréciation de l'API OpenCode** : nécessite une veille active sur les changements de l'API CLI/stdin-stdout d'OpenCode
2. **Fuite mémoire du bridge** : les processus subprocess doivent être correctement nettoyés
3. **Désynchronisation SSE** : si le bridge perd la connexion au subprocess, le stream SSE se coupe sans warning

### Mitigations

1. Tests d'intégration bridge inclus dans la CI (`tests/` adaptés au nouveau bridge)
2. Healthcheck `agentos-engine` surveillé par Docker Compose
3. `opencode_bridge.py` inclut un fallback vers le mode legacy si l'engine est injoignable
4. Documentation du protocole stdin/stdout dans `docs/master-ref/03-ARCHITECTURE-MIGRATION.md`
