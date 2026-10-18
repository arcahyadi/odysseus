# PARTIE 4 — DÉVELOPPEMENT

## 4.1 Standards de code & clean code

- La lisibilité prime sur l'intelligence apparente du code — quelqu'un d'autre (ou toi dans 6 mois) doit pouvoir le comprendre vite.
- Nommage explicite (variables, fonctions, classes) — un bon nom évite un commentaire.
- Fonctions courtes, responsabilité unique par fonction/classe.
- Commentaires : expliquer le **pourquoi** (une décision non évidente), pas le **quoi** (le code doit être assez clair pour ça).
- Adopter le style guide officiel du langage/framework utilisé plutôt que d'en inventer un.

## 4.2 Design patterns & principes

- **SOLID** : Single responsibility, Open/closed, Liskov substitution, Interface segregation, Dependency inversion.
- **DRY** (Don't Repeat Yourself), **KISS** (Keep It Simple), **YAGNI** (You Aren't Gonna Need It — ne pas complexifier pour un besoin hypothétique futur).
- Design patterns (Factory, Strategy, Observer, Repository...) : des outils utiles, pas des objectifs en soi. ⚠️ Le sur-usage de patterns pour un problème simple est aussi nuisible que leur absence sur un problème complexe.
- Préférer la composition à l'héritage quand c'est possible.

## 4.3 Stratégie de tests

- **Pyramide de tests** : beaucoup de tests unitaires (rapides, ciblés) > des tests d'intégration (moins nombreux) > peu de tests end-to-end (lents, fragiles, mais couvrent le parcours réel).
- **TDD** (Red-Green-Refactor) là où la logique métier est complexe et bénéficie d'être clarifiée par les tests d'abord.
- **BDD** (Gherkin Given/When/Then) pour aligner tests et langage métier, utile en collaboration avec des non-devs (PO, QA).
- Couverture de code : viser un niveau raisonnable (souvent cité : 70-80%) sur la logique critique, sans en faire un dogme aveugle — 100% de couverture avec des tests inutiles est pire que 70% de tests pertinents.
- Mocker/stubber les dépendances externes dans les tests unitaires ; garder de vrais appels (ou proches) dans les tests d'intégration.

## 4.4 Code review

- Objectif principal : qualité + transmission de connaissance au sein de l'équipe, pas seulement "chasse aux bugs".
- Garder les PR petites (idéalement < 400 lignes de diff) — une PR trop grosse est mal reviewée, point final.
- Checklist de review type : lisibilité, tests présents et pertinents, pas de régression évidente, respect des conventions, doc mise à jour si besoin.
- Feedback constructif : formuler en suggestion, pas en jugement ("on pourrait envisager..." plutôt que "c'est faux").
- 🏢 Définir un SLA interne de review (ex : sous 24h ouvrées) pour éviter les PR qui traînent des jours.

## 4.5 Gestion de la dette technique

- La dette technique est normale et parfois un choix délibéré (aller vite pour valider un marché) — le problème, c'est la dette **non trackée** et **jamais remboursée**.
- Tracker la dette comme des tickets à part entière (pas juste des `// TODO` perdus dans le code).
- Allouer un pourcentage récurrent du temps de sprint au remboursement de dette (souvent cité : ~15-20%).
- Éviter le "big bang rewrite" (réécriture totale) — préférer le refactoring incrémental (strangler pattern) qui garde le système fonctionnel en continu.

## 4.6 Sécurité applicative

- Connaître et appliquer l'**OWASP Top 10** (injection, authentification cassée, XSS, contrôle d'accès défaillant, etc.).
- Valider/sanitiser systématiquement les entrées utilisateur, utiliser des requêtes paramétrées (jamais de concaténation SQL brute).
- Auditer les dépendances régulièrement (Dependabot, Renovate, `npm audit`/équivalent) et patcher les vulnérabilités connues.
- Appliquer le principe du moindre privilège dans le code (permissions API, accès DB par service).

## 4.7 Performance

- Profiler avant d'optimiser — ne jamais optimiser "à l'instinct" sans mesure.
- Stratégies de cache adaptées au besoin (cache applicatif, CDN, cache DB) avec une politique d'invalidation claire.
- Lazy loading, pagination systématique sur les listes potentiellement grandes, indexation des requêtes DB fréquentes.
- Monitoring de performance (APM) mis en place dès le développement, pas seulement en prod après coup.

## 4.8 Feature flags

- Découpler **déploiement** (le code est en prod) et **release** (la fonctionnalité est visible/active) — permet de déployer en continu sans exposer une feature incomplète.
- Permet un rollout progressif (% d'utilisateurs) et un rollback instantané sans redéploiement en cas de souci.
- ⚠️ Nettoyer les flags obsolètes régulièrement — un flag oublié devient lui-même de la dette technique et un risque (code mort qui peut se réactiver).

## 4.9 Documentation continue

- Documenter le code au fil de l'eau (docstrings, JSDoc ou équivalent), pas en rattrapage en fin de projet.
- Documentation API générée/maintenue via un standard (OpenAPI/Swagger) — idéalement générée depuis le code pour rester synchronisée.
- La documentation à jour fait partie de la **Definition of Done**, pas une tâche "si on a le temps".

## ✅ Checklist fin de Partie 4

- [ ] Standards de code appliqués et vérifiés automatiquement (lint)
- [ ] Tests écrits avec la fonctionnalité, pas après coup
- [ ] Toute PR passe par une review avant merge
- [ ] Dette technique trackée dans le backlog
- [ ] Dépendances auditées régulièrement
- [ ] Documentation (code + API) à jour

> **Retour à l'index :** [README.md](./README.md)
