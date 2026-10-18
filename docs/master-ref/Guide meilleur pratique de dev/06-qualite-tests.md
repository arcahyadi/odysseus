# PARTIE 6 — QUALITÉ & TESTS

## 6.1 Plan de tests

Définir en amont : quoi tester, à quel niveau, avec quels outils, et qui est responsable (dev, QA dédiée, ou les deux).

## 6.2 Matrice des types de tests

| Type | Objectif | Qui | Quand |
|---|---|---|---|
| Unitaires | Valider une unité de code isolée | Dev | À chaque commit |
| Intégration | Valider l'interaction entre composants | Dev | À chaque PR |
| End-to-end (e2e) | Valider un parcours utilisateur complet | Dev/QA | Avant release |
| Smoke tests | Vérifier que l'essentiel fonctionne après déploiement | Automatisé | Post-déploiement |
| Régression | Vérifier qu'une correction n'a rien cassé ailleurs | Automatisé | Continu |
| Charge / performance | Valider le comportement sous forte charge | Dev/Ops | Avant release majeure |
| Sécurité | Détecter des vulnérabilités | Dev/Sécu | Continu + avant release |
| Exploratoires | Trouver des bugs non anticipés par les scénarios écrits | QA | Avant release |
| Accessibilité | Vérifier la conformité WCAG | Dev/QA | Continu |
| UAT (recette) | Validation métier finale | Client/PO | Avant mise en prod |

## 6.3 Définition du "Done"

Exemple de **Definition of Done** (à adapter) :
- Code review passée et approuvée
- Tests unitaires écrits et verts
- Pas de régression sur la suite de tests existante
- Documentation mise à jour si nécessaire
- Déployé et validé en environnement de staging

Distinguer la **Definition of Ready** (une story est-elle assez claire pour être prise en dev ?) de la **Definition of Done** (une story est-elle vraiment terminée ?).

## 6.4 QA process & bug tracking

- Cycle de vie type d'un bug : Nouveau → Confirmé → En cours → Corrigé → Vérifié → Fermé.
- Distinguer **sévérité** (impact technique/business objectif) et **priorité** (urgence de traitement décidée) — un bug très sévère peut être basse priorité s'il touche une fonctionnalité peu utilisée.
- Template de rapport de bug utile : étapes de reproduction, comportement attendu vs observé, environnement, sévérité.

## 6.5 Tests de sécurité

- **SAST** (analyse statique du code) et **DAST** (analyse dynamique en exécution) intégrés au pipeline CI/CD.
- Scan de dépendances automatisé (vulnérabilités connues des librairies utilisées).
- 🏢 Pentest (interne ou prestataire externe) avant une mise en production sensible, puis périodiquement.

## 6.6 Tests de performance / charge

- **Load testing** (charge normale attendue), **stress testing** (jusqu'à la rupture, pour connaître les limites), **soak testing** (tenue dans la durée).
- Outils courants : k6, JMeter, Gatling, Locust — le choix importe moins que le fait de tester avant un pic connu (soldes, lancement médiatisé...).

## 6.7 UAT (recette utilisateur)

- Environnement de recette dédié, proche de la prod.
- Scénarios de recette dérivés directement des critères d'acceptation définis en Partie 2.
- Sign-off explicite du client/Product Owner avant mise en production — évite les "je pensais que..." après coup.

## ✅ Checklist fin de Partie 6

- [ ] Plan de tests défini et partagé avec l'équipe
- [ ] Definition of Done appliquée systématiquement
- [ ] Pipeline CI inclut un scan sécurité automatisé
- [ ] Tests de charge réalisés avant une release à fort impact
- [ ] Recette utilisateur validée et signée avant mise en prod

> **Retour à l'index :** [README.md](./README.md)
