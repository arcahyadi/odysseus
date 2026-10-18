# PARTIE 8 — MAINTENANCE (post-livraison)

## 8.1 Monitoring & observabilité

- Trois piliers de l'observabilité : **logs** (événements détaillés), **métriques** (mesures agrégées dans le temps), **traces** (suivi d'une requête à travers le système).
- Outils courants selon le pilier : Prometheus/Grafana ou Datadog (métriques), ELK/Loki (logs), Jaeger/Tempo (traces), Sentry (erreurs applicatives).
- Dashboards clés à définir dès le lancement : santé technique (latence, taux d'erreur, saturation), et indicateurs business si pertinent.

## 8.2 Alerting & astreinte (on-call)

- Seuils d'alerte pertinents et actionnables — éviter l'"alert fatigue" (trop d'alertes non critiques qui font ignorer les vraies urgences).
- 🏢 Rotation d'astreinte formalisée avec des **runbooks** (procédures pas à pas pour les incidents connus) pour ne pas dépendre d'une seule personne qui "sait comment faire".

## 8.3 Gestion des incidents

- Process : détection → triage (sévérité) → mobilisation → résolution → communication → **post-mortem**.
- Échelle de sévérité type (SEV1 = panne totale critique, SEV4 = mineur, pas d'urgence).
- **Post-mortem sans blâme** (blameless postmortem) : l'objectif est de comprendre la chaîne de causes systémiques, pas de désigner un responsable — sinon les prochains incidents seront cachés plutôt que signalés.

## 8.4 Support & SLA

- Niveaux de support typiques : L1 (premier contact, résolution des cas simples), L2 (technique, escalade), L3 (dev/expert).
- Définitions à clarifier avec le client/stakeholders : **SLA** (engagement contractuel, ex : temps de réponse), **SLO** (objectif interne visé), **SLI** (indicateur mesuré réellement).
- Temps de réponse différenciés selon la criticité (un SEV1 n'a pas le même délai qu'une demande d'évolution mineure).

## 8.5 Sécurité continue

- Veille sur les CVE des dépendances utilisées, patching régulier (pas seulement lors d'un audit).
- Audit de sécurité périodique, pas uniquement avant le lancement initial.
- Rotation des certificats et credentials avant expiration (automatiser l'alerte d'expiration).

## 8.6 Sauvegardes & disaster recovery

- Stratégie de backup : fréquence, rétention, et surtout — **tester la restauration régulièrement** (une sauvegarde jamais restaurée n'est qu'une supposition).
- **RTO** (Recovery Time Objective : combien de temps pour repartir) et **RPO** (Recovery Point Objective : combien de données on accepte de perdre) définis selon la criticité du service.
- Plan de reprise d'activité formalisé pour les services critiques.

## 8.7 Documentation utilisateur continue

- FAQ et base de connaissance mises à jour au fil des évolutions, pas figées après le lancement.
- Lien direct entre nouvelles features livrées et mise à jour de la doc utilisateur — sinon la doc devient rapidement obsolète et perd sa valeur.

## ✅ Checklist fin de Partie 8

- [ ] Monitoring actif sur les 3 piliers (logs/métriques/traces)
- [ ] Alerting calibré (ni trop, ni trop peu)
- [ ] Process d'incident documenté avec post-mortems systématiques
- [ ] SLA/SLO définis et suivis
- [ ] Sauvegardes testées régulièrement (pas juste faites)

> **Retour à l'index :** [README.md](./README.md)
