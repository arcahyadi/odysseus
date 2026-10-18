# Runbook — Réponse aux Incidents

**Version :** 1.0
**Dernière mise à jour :** 2026-08-06
**Propriétaire :** Équipe Odysseus AgentOS

---

## 1. Détection

### Canaux de détection

| Canal | Type d'incident | Délai de détection |
|-------|----------------|:---:|
| **Healthchecks Docker** (compose) | Service down, container crash | < 30 secondes |
| **ntfy push notifications** | Alerte critique, dépassement de seuil | < 2 minutes |
| **Cockpit dashboard** | Dégradation de service, drift | < 5 minutes |
| **LangFuse traces** | Anomalie de latence, erreur LLM | < 15 minutes |
| **GitHub Security Advisories** | Vulnérabilité dans une dépendance | Variable |
| **Workflow `security-incident.yaml`** | Blocage de sécurité (`security.block`) | < 30 secondes |
| **Logs Docker** (`docker compose logs`) | Erreurs applicatives, crash loops | Manuel |
| **Utilisateur final** | Comportement anormal, erreur visible | Variable |

### Signals d'alerte automatiques

1. **Healthcheck KO** > 3 tentatives consécutives → alerte CRITICAL
2. **Taux d'erreur HTTP 5xx** > 5% sur fenêtre de 5 minutes → alerte WARNING
3. **Latence p95** > 10 secondes → alerte WARNING
4. **Blocage `security.block`** (prompt injection, accès non autorisé) → workflow `security-incident.yaml` + alerte CRITICAL
5. **Espace disque** < 10% sur un volume Docker → alerte WARNING
6. **Consommation tokens** > 80% du budget mensuel → alerte INFO

---

## 2. Triage — Niveaux de sévérité

### SEV1 — Critique

**Définition :** Arrêt complet du service. Perte de données. Faille de sécurité exploitable.

| Exemples |
|----------|
| Odysseus ne répond plus (HTTP 5xx sur toutes les routes) |
| Faille RCE exploitée via l'agent |
| Perte de la base de données sans backup |
| Compromission d'un compte admin |
| Fuite de secrets (clé API, token) exposée publiquement |

**Réponse :**
- Mobilisation immédiate (< 15 minutes)
- Communication : ntfy CRITICAL + email à tous les admins
- Gel des déploiements jusqu'à résolution
- Post-mortem obligatoire dans les 48h

### SEV2 — Majeur

**Définition :** Dégradation sévère. Service principal dégradé mais partiellement fonctionnel. Un service essentiel down.

| Exemples |
|----------|
| ChromaDB down → RAG inutilisable |
| OpenCode Engine injoignable → mode legacy forcé |
| SearXNG down → recherche web indisponible |
| Pipeline 7 phases bloqué en boucle |

**Réponse :**
- Mobilisation dans l'heure
- Communication : ntfy WARNING
- Résolution ciblée, déploiement autorisé si correctif
- Post-mortem recommandé

### SEV3 — Mineur

**Définition :** Dégradation légère. Service optionnel down. Bug non bloquant.

| Exemples |
|----------|
| Kroki down → diagrammes indisponibles |
| Scrapling MCP down → scraping web indisponible |
| n8n down → automatisation indisponible |
| Bug UI : cockpit n'affiche pas la phase courante |

**Réponse :**
- Mobilisation dans la journée
- Communication : ticket GitHub
- Correction dans le cycle normal
- Post-mortem optionnel

### SEV4 — Cosmétique

**Définition :** Aucun impact utilisateur. Amélioration continue.

| Exemples |
|----------|
| Logs trop verbeux |
| Dashboard lent (> 5s) |
| Warning dans les logs sans impact |
| Documentation manquante ou obsolète |

**Réponse :**
- Traité dans le backlog normal
- Pas de communication dédiée
- Pas de post-mortem

### Arbre de décision

```
Incident détecté
├── Service principal down ? → SEV1
├── Données compromises ? → SEV1
├── Faille de sécurité exploitable ? → SEV1
├── Service essentiel dégradé ? → SEV2
├── Service optionnel down ? → SEV3
└── Cosmétique ? → SEV4
```

---

## 3. Mobilisation

### Rôles d'intervention

| Rôle | Responsabilité | Qui (self-hosted) |
|------|---------------|-------------------|
| **Incident Commander** | Coordonne la réponse, communique avec les parties prenantes | Administrateur système |
| **Technical Lead** | Diagnostique et corrige la cause racine | Administrateur système |
| **Communications** | Informe les utilisateurs, rédige le post-mortem | Administrateur système |
| **Scribe** | Documente la timeline en temps réel | Logs + Obsidian vault |

### Procédure d'escalade

```
SEV1 → Mobilisation immédiate, tous les admins
SEV2 → Admin principal, backup dans l'heure
SEV3 → Traité dans le cycle de travail normal
SEV4 → Backlog
```

---

## 4. Résolution

### Phase 1 — Contenir (Stop the bleeding)

1. **Isoler le service affecté** : `docker compose stop <service>` si le service peut être arrêté sans perte de données
2. **Activer les kill-switches** si nécessaire (ex. `ODYSSEUS_DESTRUCTIVE_GATE=on`)
3. **Déconnecter les canaux externes** (Discord, Telegram) si l'agent émet des messages non contrôlés
4. **Prendre un snapshot** de l'état actuel :
   ```bash
   docker compose logs --tail 500 --timestamps > incident_$(date +%Y%m%d_%H%M%S).log
   docker compose cp odysseus:/app/data ./incident_data_backup
   ```

### Phase 2 — Diagnostiquer

1. **Analyser les logs** :
   ```bash
   docker compose logs odysseus --tail 200
   docker compose logs agentos-engine --tail 200
   ```
2. **Vérifier les healthchecks** :
   ```bash
   docker compose ps
   docker inspect <container> | grep -A 5 Health
   ```
3. **Vérifier l'espace disque** :
   ```bash
   docker system df
   ```
4. **Vérifier les métriques LangFuse** (si activé) → dashboard sur `http://localhost:3000`
5. **Consulter le Cockpit** → onglet Health, onglet Drift

### Phase 3 — Corriger

1. **Correctif immédiat** :
   - Redémarrage : `docker compose restart <service>`
   - Rollback : `git checkout <last_good_commit>` puis `docker compose up -d --build`
   - Kill-switch : activer/désactiver la variable d'environnement appropriée
2. **Vérifier** : `docker compose ps` → tous les services `healthy`
3. **Tester** : `curl http://localhost:7000/api/health`

### Phase 4 — Restaurer

1. **Remettre en service les composants arrêtés** : `docker compose up -d <service>`
2. **Réactiver les canaux externes** si désactivés
3. **Restaurer depuis backup** si nécessaire :
   ```bash
   docker compose cp ./backup/db.dump odysseus:/app/data/
   ```

---

## 5. Communication

### Template d'annonce d'incident

```
🚨 INCIDENT [SEV1/2/3] — Odysseus AgentOS

Statut : [En cours / Résolu]
Date : [AAAA-MM-JJ HH:MM UTC]
Impact : [Description de l'impact utilisateur]
Services affectés : [Liste]
Actions en cours : [Ce qui est fait]
Prochaine mise à jour : [Timestamp]
```

### Canaux de communication

| Canal | SEV1 | SEV2 | SEV3 | SEV4 |
|-------|:----:|:----:|:----:|:----:|
| ntfy push (CRITICAL) | ✓ | ✗ | ✗ | ✗ |
| Email admin | ✓ | ✓ | ✗ | ✗ |
| Cockpit status banner | ✓ | ✓ | ✓ | ✗ |
| GitHub issue | ✓ | ✓ | ✓ | ✓ |
| Discord/Telegram (si connecté) | ✓ | ✗ | ✗ | ✗ |

### Fréquence des mises à jour

| Sévérité | Fréquence |
|----------|:---------:|
| SEV1 | Toutes les 30 minutes |
| SEV2 | Toutes les 2 heures |
| SEV3 | 1 mise à jour à la résolution |

---

## 6. Post-mortem

### Déclencheur

Un post-mortem est **obligatoire** pour tout SEV1 et **recommandé** pour tout SEV2.

### Template

Utiliser le template `docs/governance/post-mortem-template.md`.

### Délai

- SEV1 : post-mortem publié dans les 48h suivant la résolution
- SEV2 : post-mortem publié dans les 5 jours ouvrés

---

## 7. Workflows automatisés

### `workflows/security-incident.yaml`

Le workflow de réponse aux incidents de sécurité s'exécute automatiquement sur l'événement `security.block` :

1. **Snapshot DB** : dump de la base de données → `backups/incident_<id>.dump`
2. **Capture logs** : `docker logs --tail 500` → `/var/log/incident_<id>.log`
3. **Évaluation sévérité** : l'agent `security-audit` évalue la gravité
4. **Alerte critique** : push ntfy avec priorité `critical`
5. **Rapport Obsidian** : note dans le vault `security/incidents/`
6. **Détection répétition** : compte des incidents par IP sur 24h
7. **Ban automatique** : si ≥ 3 incidents, ban IP via AdGuard pour 24h
8. **Commit Forgejo** : versionne le rapport d'incident

### `workflows/auto-heal.yaml`

Workflow d'auto-réparation pour les pannes non critiques.

### `workflows/nightly-maintenance.yaml`

Maintenance nocturne : nettoyage, compaction, vérification d'intégrité.

---

## 8. Checklist d'intervention rapide

```
□ Confirmer la sévérité (SEV1-SEV4)
□ Notifier les parties prenantes selon le canal approprié
□ Isoler le service si nécessaire (docker compose stop)
□ Capturer les logs et l'état (docker compose logs)
□ Activer les kill-switches pertinents
□ Identifier la cause racine
□ Appliquer le correctif
□ Vérifier la restauration du service (healthcheck + test manuel)
□ Communiquer la résolution
□ Planifier le post-mortem (SEV1/SEV2)
```

---

## 9. Références

- `docker-compose.yml` : configuration des services et healthchecks
- `src/killswitch_registry.py` : registre des 30+ kill-switches
- `src/service_health.py` : vérification de santé des services
- `workflows/security-incident.yaml` : réponse automatisée aux incidents de sécurité
- `SECURITY.md` : politique de sécurité
- `THREAT_MODEL.md` : modèle de menace et surface d'attaque
- `../governance/sla.md` : SLA, SLO, SLI, RTO, RPO
- `docs/governance/post-mortem-template.md` : template de rapport post-incident
