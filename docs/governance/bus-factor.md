# Analyse du Bus Factor — Odysseus AgentOS

**Version :** 1.0
**Date :** 2026-08-06
**Objectif :** Bus factor > 1 sur tous les composants critiques

---

## Définition

Le **bus factor** est le nombre minimum de personnes qui, si elles étaient soudainement indisponibles, mettraient en péril la capacité à maintenir et faire évoluer le projet. Un bus factor de 1 signifie qu'une seule personne détient toute la connaissance d'un composant — c'est un risque existentiel.

**Cible :** Bus factor ≥ 2 sur tous les composants critiques.

---

## Composants critiques et connaissance

### Cœur du système

| Composant | Fichiers clés | Complexité | Bus Factor | Connaissance primaire | Connaissance secondaire |
|-----------|-------------|:---:|:---:|-----------|------------|
| **Bridge OpenCode** | `src/opencode_bridge.py` | 🟢 Faible | 1 | Équipe core | *(à former)* |
| **Engine isolé** | `docker/agentos-engine/engine_server.py`, `Dockerfile` | 🟡 Moyenne | 1 | Équipe core | *(à former)* |
| **Event bus** | `src/event_bus.py`, `packages/sfd-eventbus/` | 🟡 Moyenne | 1 | Équipe core | *(à former)* |
| **Orchestrateur** | `src/orchestrator/` | 🔴 Élevée | 1 | Équipe core | *(à former)* |

### Infrastructure Docker

| Composant | Fichiers clés | Complexité | Bus Factor | Connaissance primaire | Connaissance secondaire |
|-----------|-------------|:---:|:---:|-----------|------------|
| **Docker Compose** | `docker-compose.yml`, `docker-compose.gpu-*.yml`, `docker-compose.isolated.yml` | 🔴 Élevée | 1 | Équipe core | *(à former)* |
| **Profils Docker** | 15 services, 8 profils | 🟡 Moyenne | 1 | Équipe core | *(à former)* |
| **gVisor sandbox** | `SECURITY.md:38-50` | 🟢 Faible | 1 | Équipe core | *(à former)* |
| **Traefik** | `docker-compose.yml:629-652` | 🟡 Moyenne | 1 | Équipe core | *(à former)* |

### Agents OpenCode

| Composant | Fichiers clés | Complexité | Bus Factor | Connaissance primaire | Connaissance secondaire |
|-----------|-------------|:---:|:---:|-----------|------------|
| **sfd-orchestrator** | `.opencode/agents/sfd-orchestrator.md` | 🟡 Moyenne | 1 | Équipe core | *(à former)* |
| **Agents pipeline** | `.opencode/agents/{planner,executor,reviewer,build,plan}.md` | 🟡 Moyenne | 1 | Équipe core | *(à former)* |
| **Agents spécialisés** | `.opencode/agents/{constitution,security-audit,edge-case-gen,gsd-*}.md` | 🟡 Moyenne | 1 | Équipe core | *(à former)* |

### Plugins npm SFD

| Composant | Fichiers clés | Complexité | Bus Factor | Connaissance primaire | Connaissance secondaire |
|-----------|-------------|:---:|:---:|-----------|------------|
| `@agentos/sfd-memory` | `packages/sfd-memory/` | 🟡 Moyenne | 1 | Équipe core | *(à former)* |
| `@agentos/sfd-durable` | `packages/sfd-durable/` | 🔴 Élevée | 1 | Équipe core | *(à former)* |
| `@agentos/sfd-security` | `packages/sfd-security/` | 🟡 Moyenne | 1 | Équipe core | *(à former)* |
| `@agentos/sfd-*` (autres) | `packages/sfd-{classify,discovery,eventbus,heartbeat,phase,prefs}/` | 🟡 Moyenne | 1 | Équipe core | *(à former)* |

### Configuration et CI/CD

| Composant | Fichiers clés | Complexité | Bus Factor | Connaissance primaire | Connaissance secondaire |
|-----------|-------------|:---:|:---:|-----------|------------|
| **CI/CD pipelines** | `.github/workflows/{ci,e2e,docker-publish,secret-scan}.yml` | 🟡 Moyenne | 1 | Équipe core | *(à former)* |
| **Workflows** | `workflows/{auto-heal,security-incident,nightly-maintenance}.yaml` | 🟡 Moyenne | 1 | Équipe core | *(à former)* |
| **Kill-switches** | `src/killswitch_registry.py` | 🟢 Faible | 1 | Équipe core | *(à former)* |
| **SFD v3.1** | `SFD.md`, `docs/master-ref/01-SFD-v3.1.md` | 🔴 Élevée | 1 | Équipe core | *(documentation écrite)* |

### UI et Frontend

| Composant | Fichiers clés | Complexité | Bus Factor | Connaissance primaire | Connaissance secondaire |
|-----------|-------------|:---:|:---:|-----------|------------|
| **Chat UI** | `static/` (162 fichiers JS) | 🔴 Élevée | 1 | Équipe core | *(à former)* |
| **Cockpit** | `static/` (composants cockpit) | 🟡 Moyenne | 1 | Équipe core | *(à former)* |
| **Settings dashboard** | `static/` (kill-switches UI) | 🟢 Faible | 1 | Équipe core | *(à former)* |

---

## Résumé

| Métrique | Valeur |
|----------|--------|
| **Nombre total de composants critiques** | 24 |
| **Composants avec bus factor = 1** | 24 (100%) |
| **Composants avec bus factor ≥ 2** | 0 (0%) |
| **Cible** | Tous les composants critiques ≥ 2 |

> ⚠️ **Alerte :** Le bus factor actuel est de 1 sur l'ensemble du projet. C'est le risque le plus critique identifié dans le registre des risques (R-05).

---

## Plan de transfert de connaissances

### Phase 1 — Documentation (immédiat, en cours)

| Action | Livrable | Statut |
|--------|----------|:------:|
| Documentation d'architecture | `docs/master-ref/03-ARCHITECTURE-MIGRATION.md` | ✅ |
| Spécification fonctionnelle | `docs/master-ref/01-SFD-v3.1.md` (1115 lignes) | ✅ |
| Documentation des services | `README.md §Services` | ✅ |
| Audit de couverture | `docs/master-ref/04-OBJECTIFS-COUVERTURE.md` | ✅ |
| Registre des risques | `docs/governance/risk-register.md` | ✅ |
| Matrice RACI | `docs/governance/raci-matrix.md` | ✅ |
| Runbook incidents | `docs/runbooks/incident-response.md` | ✅ |
| Documentation des plugins | `packages/*/README.md` | ⬜ |
| Guide de contribution | `CONTRIBUTING.md` | ✅ |
| Modèle de menace | `THREAT_MODEL.md` | ✅ |

### Phase 2 — Pairing et revues (court terme)

| Action | Durée | Priorité |
|--------|:-----:|:--------:|
| Session pairing sur le bridge OpenCode | 2h | P0 |
| Session pairing sur le Docker Compose et les profils | 2h | P0 |
| Session pairing sur l'orchestrateur et le pipeline 7 phases | 3h | P0 |
| Revue croisée du code des plugins npm SFD | 4h | P1 |
| Session pairing sur la CI/CD et les workflows | 2h | P1 |
| Session pairing sur le frontend (Chat UI + Cockpit) | 3h | P1 |

### Phase 3 — Autonomie (moyen terme)

| Action | Livrable |
|--------|----------|
| Chaque composant a au moins 2 mainteneurs identifiés | CODEOWNERS mis à jour |
| Chaque contributeur secondaire a corrigé au moins 1 bug sur le composant | Historique Git |
| Chaque contributeur secondaire a ajouté au moins 1 test | Couverture de tests |
| Exercice "chaos day" : simuler l'absence du mainteneur primaire | Rapport d'exercice |

---

## Stratégie de résilience

### Documentation comme filet de sécurité

En attendant d'atteindre un bus factor ≥ 2, les documents suivants servent de "connaissance externalisée" :

1. `docs/master-ref/` : 10 documents de référence couvrant l'architecture, les outils, la couverture, la migration, et l'état actuel
2. `docs/master-ref/01-SFD-v3.1.md` : spécification fonctionnelle de référence
3. `THREAT_MODEL.md` : modèle de menace complet
4. `SECURITY.md` : politique de sécurité et guide de déploiement
5. `README.md` : vue d'ensemble du projet
6. Tests automatisés : documentation vivante du comportement attendu

### Automatisation comme garde-fou

Les workflows automatisés réduisent la dépendance à une connaissance humaine :

- `workflows/security-incident.yaml` : réponse automatisée aux incidents
- `workflows/auto-heal.yaml` : auto-réparation
- `workflows/nightly-maintenance.yaml` : maintenance préventive
- `.github/workflows/ci.yml` : tests automatisés à chaque PR
- `.github/workflows/secret-scan.yml` : détection automatique de secrets
- Healthchecks Docker : détection automatique des pannes

---

## CODEOWNERS recommandé

Voir le fichier `CODEOWNERS` à la racine du dépôt pour la configuration GitHub.

### Chemins critiques

| Chemin | Responsable primaire | Responsable secondaire |
|--------|---------------------|------------------------|
| `src/orchestrator/` | @equipe-core | *(à désigner)* |
| `src/opencode_bridge.py` | @equipe-core | *(à désigner)* |
| `docker/` | @equipe-core | *(à désigner)* |
| `docker-compose*.yml` | @equipe-core | *(à désigner)* |
| `packages/` | @equipe-core | *(à désigner)* |
| `.github/workflows/` | @equipe-core | *(à désigner)* |
| `workflows/` | @equipe-core | *(à désigner)* |
| `.opencode/` | @equipe-core | *(à désigner)* |
| `static/` | @equipe-core | *(à désigner)* |
