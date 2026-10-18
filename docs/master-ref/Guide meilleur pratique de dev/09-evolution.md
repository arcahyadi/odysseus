# PARTIE 9 — ÉVOLUTION & NOUVELLES FONCTIONNALITÉS

## 9.1 Processus d'ajout de features

- Chaque nouvelle fonctionnalité significative rejoue un **mini-cycle** : cadrage léger → conception → dev → tests → déploiement.
- Analyse d'impact sur l'existant avant de démarrer : architecture actuelle, performance, sécurité, dette technique induite.
- Pour les features majeures, un document **RFC** (Request For Comments) partagé à l'équipe avant le début du dev permet de récolter les objections tôt, quand elles coûtent encore peu cher à intégrer.

## 9.2 Feedback utilisateur & analytics

- Collecte multi-canal : interviews utilisateurs, enquêtes, feedback in-app, tickets support.
- Analytics produit (funnels de conversion, rétention, usage réel des fonctionnalités) pour prioriser sur des faits plutôt que des intuitions.
- Approche "data-informed" plutôt que "data-driven" pur : la donnée éclaire la décision, elle ne la remplace pas entièrement (le contexte et le jugement humain comptent aussi).

## 9.3 Refactoring continu

- Règle du "boy scout" : laisser le code un peu plus propre qu'on ne l'a trouvé à chaque passage, plutôt que d'attendre un gros chantier dédié.
- Refactoring planifié (dette identifiée et priorisée) et refactoring opportuniste (au fil du développement) se complètent.

## 9.4 Migration & montées de version

- Anticiper les migrations de dépendances majeures (langage, framework) plutôt que de les subir en urgence quand une version devient obsolète/non maintenue.
- Pour les migrations de données en production : pattern **expand/contract** (ajouter le nouveau schéma en parallèle, migrer les données, basculer le code, puis seulement retirer l'ancien schéma) pour éviter tout downtime.

## 9.5 Dépréciation & fin de vie

- Politique de dépréciation claire : préavis suffisant, communication explicite aux utilisateurs/consommateurs de l'API.
- Versioning d'API explicite si des consommateurs externes dépendent du système, avec période de transition documentée avant suppression de l'ancienne version.

## 9.6 Scalabilité de l'équipe & du produit

- La **loi de Conway** : l'architecture du système finit par refléter la structure de communication de l'organisation — en tenir compte en amont plutôt que de le subir.
- Scinder une équipe/un système seulement quand la douleur (coordination, taille du code, vitesse de livraison) le justifie réellement — anticiper trop tôt mène à de l'over-engineering coûteux et à une complexité inutile.

## ✅ Checklist fin de Partie 9

- [ ] Chaque nouvelle feature majeure repasse par une mini-conception
- [ ] Feedback utilisateur collecté et exploité dans les priorisations
- [ ] Refactoring intégré en continu, pas repoussé indéfiniment
- [ ] Migrations de données planifiées sans downtime
- [ ] Politique de dépréciation communiquée en amont

> **Retour à l'index :** [README.md](./README.md)
