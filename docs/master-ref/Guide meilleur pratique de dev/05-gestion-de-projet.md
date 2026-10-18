# PARTIE 5 — GESTION DE PROJET (transversal, du début à la fin)

## 5.1 Méthodologies en détail

**Scrum** : équipe fixe, sprints de longueur fixe (souvent 1-2 semaines), rôles définis (Product Owner, Scrum Master, équipe de dev), cérémonies structurées.

**Kanban** : flux continu, pas de sprint fixe, limites de **Work In Progress (WIP)** par colonne pour éviter la surcharge, priorisation continue du backlog.

**Hybrides (Scrumban)** : cadence Scrum + flexibilité Kanban — souvent le choix pragmatique pour les petites équipes.

🧍 Solo/petite équipe : Kanban simple, cérémonies allégées (pas besoin d'un Scrum Master dédié).
🏢 Grande organisation multi-équipes : SAFe ou équivalent pour synchroniser plusieurs équipes Scrum entre elles (PI Planning, Scrum of Scrums).

## 5.2 Cérémonies agiles

| Cérémonie | Fréquence | Objectif | Durée type |
|---|---|---|---|
| Sprint planning | Début de sprint | Définir l'objectif et le contenu du sprint | 1-2h par semaine de sprint |
| Daily standup | Quotidien | Synchroniser l'équipe (pas un reporting au manager) | 15 min max |
| Sprint review / démo | Fin de sprint | Montrer l'incrément aux parties prenantes | 30-60 min |
| Rétrospective | Fin de sprint | Améliorer le fonctionnement d'équipe | 45-60 min |
| Backlog refinement | Continu / mi-sprint | Clarifier et affiner les prochains items | 30-60 min |

- Rétrospective : formats utiles — Start/Stop/Continue, "4 L" (Liked/Learned/Lacked/Longed for) — varier le format pour éviter la routine qui tue l'engagement.

## 5.3 Gestion du backlog

- Critère **INVEST** pour une bonne user story : Independent, Negotiable, Valuable, Estimable, Small, Testable.
- Priorisation continue : MoSCoW, RICE, ou simple Valeur vs Effort.
- Le backlog n'est jamais figé — il vit et se réordonne en fonction des apprentissages.

## 5.4 Estimation

- Story points (complexité relative) plutôt que temps brut (moins biaisé par l'interruption/le contexte).
- **Planning Poker** pour estimer collectivement et faire émerger les désaccords (souvent plus riches d'infos que le chiffre lui-même).
- La **vélocité** d'une équipe ne se compare jamais entre équipes différentes — c'est une mesure interne relative, pas absolue.

## 5.5 Suivi & reporting

- Métriques agiles utiles : vélocité, burndown/burnup chart, cycle time, lead time.
- **DORA metrics** (référence reconnue pour la performance des équipes tech) : fréquence de déploiement, délai de mise en prod, taux d'échec des changements, temps moyen de restauration (MTTR).
- Adapter le format de reporting à l'audience : un board Kanban pour l'équipe, un résumé synthétique pour les stakeholders non-techniques.

## 5.6 Gestion des risques continue

- Le registre des risques créé en Partie 1 se met à jour à chaque point d'étape, pas une fois pour toutes.
- Revoir périodiquement : nouveaux risques apparus, risques caducs, efficacité des mitigations en place.

## 5.7 Communication & stakeholders

- Matrice RACI tenue à jour si les rôles évoluent.
- Plan de communication explicite : qui a besoin de quelle info, à quelle fréquence, sous quel format.
- Gérer les attentes activement — un stakeholder mal informé invente ses propres suppositions, en général plus optimistes que la réalité.

## 5.8 Gestion du changement (scope creep)

- Toute demande de changement en cours de projet passe par une **analyse d'impact** (délai, coût, qualité) avant acceptation — le triangle qualité/coût/délai ne permet pas de tout ajouter sans conséquence sur un des trois axes.
- Formaliser même légèrement une demande de changement (change request) évite les dérives silencieuses de périmètre.

## Bonnes pratiques récap — Partie 5

- [ ] Cérémonies régulières et respectées dans leur timebox
- [ ] Backlog priorisé et affiné en continu
- [ ] Registre des risques vivant, pas figé
- [ ] Reporting adapté à chaque audience
- [ ] Toute demande de changement passe par une analyse d'impact

> **Retour à l'index :** [README.md](./README.md)
