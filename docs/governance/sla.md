# Service Level Agreement (SLA) — Odysseus AgentOS

**Version :** 1.0
**Date d'effet :** 2026-08-06
**Périmètre :** Déploiement self-hosted standard (Docker Compose, 15 services)

---

## Définitions

| Terme | Définition |
|-------|-----------|
| **SLO** (Service Level Objective) | Objectif de fiabilité cible sur une période glissante de 28 jours |
| **SLI** (Service Level Indicator) | Métrique mesurée pour évaluer le SLO |
| **SLA** (Service Level Agreement) | Contrat global incluant SLO, RTO, RPO, et pénalités |
| **RTO** (Recovery Time Objective) | Durée maximale acceptable pour restaurer le service après un incident |
| **RPO** (Recovery Point Objective) | Perte de données maximale acceptable (en temps) |
| **Disponibilité** | Pourcentage du temps où le service répond aux requêtes avec succès (HTTP 2xx/3xx) |

---

## Services et leurs SLA

### 1. Odysseus Core (FastAPI + OpenCode Bridge)

| Métrique | Cible |
|----------|-------|
| **SLO — Disponibilité** | 99,5% (max 3h36min d'indisponibilité par mois) |
| **SLO — Latence p95** | < 2 secondes pour les réponses chat (hors streaming LLM) |
| **SLO — Latence p99** | < 5 secondes |
| **SLI — Disponibilité** | `GET /api/health` → 200 OK, mesuré toutes les 60s |
| **SLI — Latence** | `GET /api/health` → temps de réponse, mesuré toutes les 60s |
| **RTO** | 30 minutes |
| **RPO** | 5 minutes (pertes de sessions in-memory acceptables, données persistées intactes) |
| **Healthcheck** | `docker-compose.yml:184-189` — intervalle 15s, timeout 10s, 5 retries |
| **Dépendances** | ChromaDB, SearXNG (dépend au démarrage) |

### 2. AgentOS Engine (OpenCode Engine isolé)

| Métrique | Cible |
|----------|-------|
| **SLO — Disponibilité** | 99,0% (max 7h12min d'indisponibilité par mois) |
| **SLO — Latence p95** | < 500ms pour `/health` |
| **SLI — Disponibilité** | `GET /health` → 200 OK, mesuré toutes les 60s |
| **RTO** | 15 minutes (redémarrage conteneur) |
| **RPO** | 0 — pas de données persistées dans l'engine (stateful dans le workspace) |
| **Fallback** | Mode legacy intégré dans `opencode_bridge.py:36-38` si engine injoignable |
| **Dépendances** | agentos-sandbox |

### 3. AgentOS Sandbox (exécution isolée)

| Métrique | Cible |
|----------|-------|
| **SLO — Disponibilité** | 99,0% |
| **SLI — Disponibilité** | Conteneur running (Docker healthcheck) |
| **RTO** | 10 minutes |
| **RPO** | 0 — workspace persistant dans `agentos-sandbox-data` |
| **Référence** | `docker-compose.yml:718-740` |

### 4. ChromaDB (Vector Store)

| Métrique | Cible |
|----------|-------|
| **SLO — Disponibilité** | 99,5% |
| **SLI — Disponibilité** | `TCP port 8000` ouvert, mesuré toutes les 30s |
| **RTO** | 15 minutes |
| **RPO** | 0 — données persistées dans `chromadb-data` |
| **Alternatives** | Qdrant (`ODYSSEUS_QDRANT=on`) comme fallback |
| **Référence** | `docker-compose.yml:191-208` |

### 5. SearXNG (Meta-Search Engine)

| Métrique | Cible |
|----------|-------|
| **SLO — Disponibilité** | 99,0% |
| **SLI — Disponibilité** | `GET /` → 200 OK, mesuré toutes les 5s |
| **RTO** | 10 minutes |
| **RPO** | 0 — pas de données persistées critiques |
| **Note** | Bloquant au démarrage d'Odysseus (`depends_on: condition: service_healthy`) |
| **Référence** | `docker-compose.yml:211-253` |

### 6. Base de données (SQLite / PostgreSQL)

| Métrique | Cible |
|----------|-------|
| **SLO — Disponibilité** | 99,9% (SQLite embarqué) / 99,5% (PostgreSQL externalisé) |
| **RTO** | 5 minutes (SQLite) / 30 minutes (PostgreSQL avec restore) |
| **RPO** | 1 heure (backup automatique configurable) |
| **Note** | SQLite par défaut (`DATABASE_URL=sqlite:///./data/app.db`), PostgreSQL via profil `production` |
| **Référence** | `docker-compose.yml:45` (DATABASE_URL), `docker-compose.yml:655-683` (PostgreSQL) |

### 7. Services optionnels (profil Docker)

| Service | Profil | SLO — Disponibilité | RTO | RPO |
|---------|--------|:---:|:---:|:---:|
| **Scrapling MCP** | `scrapling` | 99,0% | 10 min | 0 |
| **ntfy** | `default` | 99,5% | 10 min | 0 |
| **Kroki** | `default` | 99,0% | 10 min | 0 |
| **Serena MCP** | `default` | 99,0% | 15 min | 0 |
| **CBM** (codebase-memory) | `knowledge` | 99,0% | 15 min | 0 |
| **Graphify** | `default` | 99,0% | 15 min | 0 |
| **LangFuse** | `observability` | 99,0% | 30 min | 5 min |
| **n8n** | `automation` | 99,0% | 15 min | 1 heure |
| **OPA** | `security` | 99,5% | 10 min | 0 |
| **Traefik** | `gateway` | 99,9% | 10 min | 0 |
| **LocalAI** | `localai` | 99,0% | 15 min | 0 |
| **Qdrant** | `vectordb` | 99,5% | 15 min | 0 |
| **Meilisearch** | `default` | 99,5% | 15 min | 0 |
| **Decision Engine** | `decision-engine` | 99,0% | 15 min | 0 |
| **PostgreSQL** | `production` | 99,5% | 30 min | 1 heure |

---

## Fenêtres de maintenance

| Type | Fréquence | Durée max | Préavis | Impact |
|------|----------|:--------:|:-------:|--------|
| **Mise à jour mineure** | Hebdomadaire (lundi 2h-4h UTC) | 30 min | Aucun | Aucun (rolling restart Docker) |
| **Mise à jour majeure** | Mensuelle | 2 heures | 48h via ntfy | Courtes interruptions (< 5 min) pendant `docker compose up -d` |
| **Maintenance infrastructure** | Trimestrielle | 4 heures | 1 semaine | Possible indisponibilité totale planifiée |
| **Correctif de sécurité critique** | À la demande | 1 heure | 1 heure | Possible indisponibilité partielle |

---

## Surveillance et alerting

| Niveau | Condition | Canal | Délai |
|--------|-----------|-------|:-----:|
| **INFO** | Dépassement SLO < 10% | Logs uniquement | — |
| **WARNING** | Service en degraded state | Cockpit dashboard | < 5 min |
| **CRITICAL** | Service down > 5 min | ntfy push + email | < 2 min |
| **EMERGENCY** | Incident sécurité SEV1-SEV2 | ntfy critical + workflow `security-incident.yaml` | < 30s |

### Métriques surveillées

- **Healthchecks Docker** : toutes les 15-30s selon le service
- **Disponibilité API** : `GET /api/health` toutes les 60s
- **Latence p95/p99** : agrégation sur fenêtre glissante de 5 minutes
- **Taux d'erreur** : ratio HTTP 5xx / total requêtes
- **Consommation tokens** : agrégation quotidienne via `ODYSSEUS_UNIFIED_TOKENS`
- **Espace disque** : volumes Docker, logs, workspace sandbox

---

## Exclusions

Le SLA ne couvre pas :
- Les pannes des fournisseurs LLM externes (OpenAI, Anthropic, DeepSeek, etc.)
- Les problèmes de connectivité réseau du côté client
- Les dégradations liées à une configuration personnalisée non standard
- Les interruptions planifiées annoncées avec le préavis requis
- Les environnements de développement local (mode legacy)

---

## Responsabilités

### Responsabilités d'Odysseus AgentOS (auto-hébergé)

Dans un déploiement self-hosted, c'est l'administrateur du système qui est responsable de :
- Maintenir l'infrastructure Docker fonctionnelle
- Appliquer les mises à jour de sécurité
- Surveiller les métriques et réagir aux alertes
- Configurer les backups de `data/`
- Maintenir le `docker-compose.yml` à jour

L'équipe Odysseus fournit :
- Les images Docker et le code source
- La documentation de déploiement (`docs/operations/setup.md`, `SECURITY.md`)
- Les mises à jour de sécurité via le dépôt GitHub
- Le canal de signalement des vulnérabilités (GitHub Security Advisories)
