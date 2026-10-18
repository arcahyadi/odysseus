# Personas — Odysseus AgentOS

**Version :** 1.0
**Date :** 2026-08-06

---

## Persona 1 : Alex — Développeur solo

### Background

| Attribut | Valeur |
|----------|--------|
| **Âge** | 28 ans |
| **Profession** | Développeur full-stack freelance |
| **Expérience technique** | 6 ans — Python, TypeScript, React, Docker |
| **Environnement** | MacBook Pro M2, 32 Go RAM, VS Code |
| **Projets types** | SaaS B2B, applications web, scripts d'automatisation |

### Objectifs

- **Automatiser les tâches répétitives** : génération de boilerplate, configuration de projets, scripts de déploiement, correction de bugs simples
- **Accélérer le prototypage** : pouvoir décrire une fonctionnalité et obtenir une implémentation fonctionnelle en quelques minutes
- **Externaliser la recherche** : ne pas passer 2 heures à lire la documentation d'une API — l'agent le fait
- **Garder le contrôle** : l'agent propose, Alex dispose. Il veut voir et approuver les changements avant qu'ils ne soient appliqués
- **Apprendre en faisant** : l'agent explique ses choix, Alex monte en compétence

### Points de douleur

- **Contexte limité des LLMs publics** : ChatGPT ne connaît pas sa codebase, son style, ses préférences
- **Friction outil** : passer de l'IDE au chat, copier-coller le code, tester, répéter — 30% du temps perdu en commutation de contexte
- **Modèles coûteux** : les API cloud (GPT-4, Claude) coûtent 50-200€/mois pour un usage intensif — il veut du local
- **Manque de mémoire** : chaque session recommence de zéro, l'agent ne retient rien de ses projets précédents
- **Insécurité** : il craint que l'agent écrase son code ou expose ses secrets

### Usage d'Odysseus

```
MATIN : "Crée un projet FastAPI avec auth JWT, SQLAlchemy, et tests pytest"
 → Pipeline SFD complet (CLASSIFY→KNOW→PLAN→BUILD→QUALITY)

APRÈS-MIDI : "Dans mon projet e-commerce, ajoute un endpoint de recherche avec filtres"
 → L'agent lit le codebase via CBM + Serena, propose un plan, exécute

SOIR : "J'ai ce bug (copie l'erreur) — trouve et corrige"
 → Mode debug avec gsd-debugger
```

### Configuration type

- `AUTH_ENABLED=true` (accès localhost uniquement)
- `ODYSSEUS_DESTRUCTIVE_GATE=on`
- Modèle local (Ollama) pour les tâches simples, API cloud pour les tâches complexes
- Kill-switches activés : `PHASE_TRACKER`, `AUTOEVAL`, `CHECKPOINT`
- UI Cockpit pour suivre la progression

---

## Persona 2 : Maria — Tech Lead / Architecte

### Background

| Attribut | Valeur |
|----------|--------|
| **Âge** | 35 ans |
| **Profession** | Tech Lead / Software Architect |
| **Expérience technique** | 12 ans — architecture distribuée, cloud (AWS/GCP), équipes de 5-15 développeurs |
| **Environnement** | Linux (Ubuntu), serveur dédié avec GPU NVIDIA RTX 4090 |
| **Projets types** | Microservices, migration cloud, refonte d'architecture |

### Objectifs

- **Déléguer les POCs** : "Évalue 3 approches pour migrer notre auth de JWT à OAuth2 avec un rapport comparatif"
- **Auditer la qualité** : l'agent doit reviewer automatiquement les PRs de son équipe, vérifier les invariants d'architecture
- **Documenter l'existant** : l'agent analyse le codebase et génère/maintenit la documentation d'architecture
- **Coordonner des sous-projets** : décomposer un projet complexe en worktrees isolés avec des agents spécialisés
- **Gérer les dépendances** : l'agent surveille les CVE, propose et teste les mises à jour

### Points de douleur

- **Trop de réunions** : 40% de son temps en réunions, 20% en revue de code — elle veut automatiser la revue
- **Dette technique invisible** : des patterns incohérents s'accumulent sans qu'elle les voie
- **Onboarding coûteux** : chaque nouveau développeur prend 2-3 semaines à comprendre l'architecture — l'agent devrait servir de mentor
- **Décisions non documentées** : pourquoi a-t-on choisi Redis plutôt que RabbitMQ en 2025 ? Personne ne s'en souvient
- **Sécurité** : elle est responsable des failles — elle veut un audit automatique à chaque PR

### Usage d'Odysseus

```
HEBDO : "Analyse les 15 PRs de la semaine et génère un rapport de qualité"
 → L'agent exécute le pipeline QUALITY sur chaque PR, synthétise les patterns

MENSUEL : "Audite la codebase avec STRIDE + OWASP Top 10"
 → Agent security-audit + rapport LangFuse

PROJET : "Migre le module de paiement vers une archi event-driven — fais un PoC"
 → Pipeline complet avec worktrees isolés, l'agent expérimente sans toucher à main
```

### Configuration type

- Déploiement sur serveur dédié avec GPU
- `POSTGRES_PASSWORD` configuré, PostgreSQL en production
- `ODYSSEUS_GVISOR_RUNTIME=runsc` pour l'isolation MCP
- LangFuse activé (`ODYSSEUS_LANGFUSE=on`) pour le tracing
- n8n activé pour les workflows d'automatisation
- Profil `decision-engine` activé
- Constitution agent vérifie tous les outputs

---

## Persona 3 : Sam — DevOps / SRE Engineer

### Background

| Attribut | Valeur |
|----------|--------|
| **Âge** | 31 ans |
| **Profession** | DevOps / Site Reliability Engineer |
| **Expérience technique** | 8 ans — Docker, Kubernetes, Terraform, CI/CD, monitoring |
| **Environnement** | Homelab avec Proxmox, 3 nœuds, GPU AMD |
| **Projets types** | Infrastructure as Code, pipelines CI/CD, monitoring, auto-healing |

### Objectifs

- **Automatiser l'infrastructure** : "Génère un docker-compose pour ce nouveau service avec healthchecks, volumes, et sécurité"
- **Superviser proactivement** : l'agent surveille les logs et les métriques, détecte les anomalies avant qu'elles ne deviennent des incidents
- **Auto-réparation** : quand un service tombe, l'agent diagnostique et tente une réparation automatique
- **Runbooks exécutables** : au lieu de suivre un runbook manuellement, l'agent l'exécute
- **Rapports de capacité** : "Prédis quand mon volume ChromaDB sera plein et propose un plan de scaling"

### Points de douleur

- **Alert fatigue** : 200 alertes par jour, 95% de faux positifs — il veut des alertes intelligentes
- **Documentation obsolète** : le runbook dit "redémarrer le service", mais le nom du conteneur a changé il y a 6 mois
- **Pas de temps pour l'automatisation** : toujours en mode pompier, jamais le temps de construire les automatisations qui l'empêcheraient d'être en mode pompier
- **Complexité du stack** : 15 services Docker, chacun avec ses propres logs, healthchecks, configurations — difficile d'avoir une vue d'ensemble
- **Updates risquées** : chaque `docker compose pull` est un saut dans l'inconnu — il veut un filet de sécurité

### Usage d'Odysseus

```
QUOTIDIEN : "Vérifie l'état de tous les services et alerte si anomalie"
 → Cockpit dashboard + workflow nightly-maintenance

HEBDO : "Analyse les 5000 dernières lignes de logs et détecte les patterns anormaux"
 → Agent explore + gsd-debugger

INCIDENT : Le conteneur agentos-engine est down
 → Le workflow auto-heal.yaml capture les logs, diagnostique, tente une correction
 → Si échec, escalade à Sam avec un diagnostic pré-établi
```

### Configuration type

- Déploiement sur homelab avec Proxmox
- GPU AMD → `docker-compose.gpu-amd.yml`
- Profil `production` : PostgreSQL + backups
- Profil `gateway` : Traefik avec Let's Encrypt
- OPA activé (`ODYSSEUS_OPA=on`)
- `ODYSSEUS_AGENTSEAL=on` pour le scellement des décisions
- Tous les kill-switches de gouvernance activés
- ntfy configuré pour les alertes push sur son téléphone
- Workflows `auto-heal.yaml` et `nightly-maintenance.yaml` actifs

---

## Synthèse des besoins par persona

| Besoin | Alex (Solo Dev) | Maria (Tech Lead) | Sam (DevOps) |
|--------|:--:|:--:|:--:|
| Exécution de code | ★★★★★ | ★★★☆☆ | ★★★★☆ |
| Revue de code automatique | ★★★☆☆ | ★★★★★ | ★☆☆☆☆ |
| Recherche et documentation | ★★★★☆ | ★★★★★ | ★★★☆☆ |
| Orchestration multi-agent | ★☆☆☆☆ | ★★★★★ | ★★★☆☆ |
| Sandbox et sécurité | ★★★☆☆ | ★★★★★ | ★★★★★ |
| Monitoring et alerting | ★★☆☆☆ | ★★★☆☆ | ★★★★★ |
| Auto-réparation | ★★★☆☆ | ★★★★☆ | ★★★★★ |
| Mémoire et apprentissage | ★★★★★ | ★★★★★ | ★★★☆☆ |
| Préférences persistantes | ★★★★☆ | ★★★★☆ | ★★☆☆☆ |
| Mode local (pas d'API cloud) | ★★★★☆ | ★★☆☆☆ | ★★★★★ |
| Multi-canal (Discord, email) | ★☆☆☆☆ | ★★★☆☆ | ★★★★☆ |
