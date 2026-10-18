# ADR-0002 : Pipeline SFD en 7 phases pour l'exécution agent

**Statut :** Accepté

**Date :** 2026-07-24

**Décideurs :** Équipe Odysseus AgentOS

---

## Contexte

La Spécification Fonctionnelle Détaillée **v3.1** (`docs/master-ref/01-SFD-v3.1.md`) définit 22 principes invariants et un modèle d'exécution en phases. Pour implémenter cette vision, nous avions besoin d'un pipeline d'exécution structuré, observable et interrompible qui garantisse :

- **Principe P8** : le plan passe les mêmes validations que toute autre action
- **Principe P14** : toute action longue survit à une panne (exécution durable)
- **Principe P15** : on n'observe pas ce qu'on ne trace pas (traçabilité complète)
- **Principe P9** : évaluer le harnais, pas seulement le modèle

### Problème

L'ancien `agent_loop.py` (3 992 lignes) implémentait un pipeline ad-hoc où les phases étaient entremêlées avec la logique LLM, rendant impossible :
- L'observation indépendante de chaque phase
- L'interruption/reprise propre entre phases
- L'ajout de nouvelles phases sans refonte
- Le test isolé de chaque phase

---

## Décision

**Nous adoptons un pipeline en 7 phases explicites, chaque phase étant un agent spécialisé distinct avec des permissions, outils et modèles assignés.**

### Les 7 phases

```
CLASSIFY → KNOW → PLAN → BUILD → QUALITY → AUTOEVAL → MEMORY_OBSERVE
```

| Phase | Agent | Rôle | Modèle | Outils | Permissions |
|-------|-------|------|--------|--------|-------------|
| **CLASSIFY** | sfd-orchestrator | Classer la requête, estimer le risque, router | deepseek-v4-pro | `sfd-classify` | Lecture seule |
| **KNOW** | explore / scout | Rechercher le contexte, lire le codebase, explorer | minimax-m3 | CBM, Serena, Scrapling | Lecture seule |
| **PLAN** | planner | Décomposer en objectifs → tâches, estimer le budget | deepseek-v4-pro | `sfd-plan`, bloc-notes | Écriture dans `.planning/` |
| **BUILD** | executor / opencoder | Écrire le code, exécuter les commandes | minimax-m3 | Bash, Write, Edit, MCP | Écriture dans workspace |
| **QUALITY** | reviewer / test-engineer | Tests, lint, analyse statique, audit sécurité | deepseek-v4-pro | Bash, Lint, Test | Lecture + exécution tests |
| **AUTOEVAL** | auto-evolve | Évaluer le résultat, décider keep/revert | deepseek-v4-pro | `sfd-autoeval`, CodeBurn | Lecture seule |
| **MEMORY_OBSERVE** | auto-evolve | Extraire les leçons, mettre à jour la mémoire | deepseek-v4-pro | `sfd-memory`, `sfd-prefs` | Écriture mémoire |

### Verrouillage de phase (phase-lock)

Chaque phase a des permissions strictes, imposées par l'infrastructure (Docker, sandbox) et non par le prompt :

| Phase | Lecture code | Écriture code | Exécution bash | Écriture mémoire | Accès réseau |
|-------|:---:|:---:|:---:|:---:|:---:|
| CLASSIFY | ✓ | ✗ | ✗ | ✗ | ✓ |
| KNOW | ✓ | ✗ | ✗ | ✗ | ✓ |
| PLAN | ✓ | ✓ (`.planning/`) | ✗ | ✗ | ✓ |
| BUILD | ✓ | ✓ | ✓ | ✗ | ✓ |
| QUALITY | ✓ | ✗ | ✓ (tests) | ✗ | ✗ |
| AUTOEVAL | ✓ | ✗ | ✗ | ✗ | ✗ |
| MEMORY_OBSERVE | ✓ | ✗ | ✗ | ✓ | ✗ |

### Kill-switches par phase

Chaque phase peut être désactivée individuellement via les variables d'environnement dans `docker-compose.yml` :

```yaml
ODYSSEUS_PHASE_TRACKER=off     # Désactive le tracking de phase
ODYSSEUS_AUTOEVAL=off          # Désactive l'auto-évaluation
ODYSSEUS_GOVERNANCE_ANCESTRY=off # Désactive le tracking d'ascendance
ODYSSEUS_CHECKPOINT=off        # Désactive les checkpoints
ODYSSEUS_DESTRUCTIVE_GATE=on   # Garde-fou opérations destructrices (ON par défaut)
```

### Transition entre phases

Les transitions sont pilotées par :
1. **Event bus** (`@agentos/sfd-eventbus`) : émet des événements `phase.entered`, `phase.completed`, `phase.failed`
2. **SSE** vers le cockpit : le frontend reçoit la progression en temps réel
3. **Checkpoints** : persistance optionnelle post-phase dans Obsidian
4. **Interruption LangGraph** : pause avant BUILD si risque classé DESTRUCTIVE

### Référence d'implémentation

- `src/killswitch_registry.py` : registre des 30+ kill-switches catégorisés (Orchestration, Governance/Memory, RAG, Document Processing, Channels, etc.)
- `src/orchestrator/` : implémentation du phase tracker et des boucles
- `packages/sfd-phase/` : plugin npm de gestion de phase
- `packages/sfd-eventbus/` : bus d'événements entre phases
- `.opencode/agents/sfd-orchestrator.md` : définition de l'agent orchestrateur
- `.opencode/tools/sfd-phase.ts` : outil custom de gestion de phase

---

## Conséquences

### Positives

1. **Observabilité native** : chaque phase émet des traces structurées
2. **Reprise après panne** : la couche d'exécution durable (`@agentos/sfd-durable`) reprend à la dernière phase validée
3. **Modèles spécialisés par phase** : un modèle léger pour BUILD, un modèle puissant pour PLAN et AUTOEVAL
4. **Permissions granulaires** : la phase BUILD ne peut pas modifier la mémoire, la phase PLAN ne peut pas exécuter de code
5. **Interruption propre** : une phase peut être interrompue sans corruption d'état
6. **Parallélisation possible** : les phases KNOW et PLAN peuvent s'exécuter en parallèle

### Négatives

1. **Latence de pipeline** : chaque transition de phase ajoute un appel modèle pour la décision de transition
2. **Complexité de débogage** : un échec en phase BUILD peut être dû à un mauvais plan de la phase PLAN
3. **Coût en tokens** : le pipeline complet consomme plus de tokens qu'un agent unique sans phases
4. **Dépendances entre phases** : une erreur de classification en CLASSIFY peut faire dérailler tout le pipeline

### Risques

1. **Boucle infinie** : si AUTOEVAL rejette systématiquement, le pipeline boucle BUILD→QUALITY→AUTOEVAL indéfiniment
2. **Dépassement de budget** : les 7 phases consomment un budget cumulatif imprévisible

### Mitigations

1. Budget maximum par pipeline configuré dans `src/budget_enforcer.py`
2. Limite de 3 itérations BUILD→QUALITY→AUTOEVAL avant escalade humaine
3. Tracing complet via LangFuse (profil `observability` dans Docker Compose)
4. Kill-switch `ODYSSEUS_LIVE_ORCHESTRATION` pour désactiver tout le pipeline
