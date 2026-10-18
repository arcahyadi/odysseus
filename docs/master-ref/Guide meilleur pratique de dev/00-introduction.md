# PARTIE 0 — Vue d'ensemble du cycle de vie

| # | Phase | Objectif | Livrables clés |
|---|-------|----------|-----------------|
| 1 | Avant-projet | Comprendre le besoin, cadrer | Charte de projet, étude de faisabilité |
| 2 | Conception | Définir quoi et comment construire | Specs, architecture, maquettes, ADR |
| 3 | Initialisation | Poser les fondations techniques | Repo, CI/CD, environnements |
| 4 | Développement | Construire le produit | Code, tests, doc |
| 5 | Gestion de projet | Piloter (transversal, du début à la fin) | Backlog, reporting, roadmap |
| 6 | Qualité & Tests | Garantir la fiabilité | Plan de tests, recette |
| 7 | Déploiement | Livrer en production | Release, changelog |
| 8 | Maintenance | Garder le système en vie et sain | Monitoring, support, patchs |
| 9 | Évolution | Faire grandir le produit | Nouvelles features, refactoring |
| 10 | Culture | Faire grandir l'équipe (transversal) | Onboarding, doc, mentorat |

Le cycle n'est pas strictement linéaire : les phases 2 à 9 se rejouent en miniature à chaque nouvelle fonctionnalité majeure, tandis que 5 et 10 sont transversales du premier au dernier jour.

```
AVANT-PROJET → CONCEPTION → SETUP → DÉVELOPPEMENT → QUALITÉ → DÉPLOIEMENT → MAINTENANCE
                    ↑                                                          |
                    └────────────────── ÉVOLUTION (nouvelle feature) ←─────────┘

        [ GESTION DE PROJET transversale sur tout le cycle ]
        [ CULTURE / COLLABORATION transversale sur tout le cycle ]
```

> **Retour à l'index :** [README.md](./README.md)
