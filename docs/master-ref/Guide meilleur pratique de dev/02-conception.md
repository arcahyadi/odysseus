# PARTIE 2 — CONCEPTION (Design & Architecture)

## 2.1 Spécifications fonctionnelles

- Rédiger des **user stories** au format "En tant que [rôle], je veux [action] afin de [bénéfice]".
- Regrouper en **Epics** > **Features** > **User stories** > **Tasks**.
- Critères d'acceptation au format **Gherkin** (Given/When/Then) pour lever l'ambiguïté.
- Wireframes bas-fidélité pour valider les parcours avant tout visuel poussé.
- Prioriser avec **MoSCoW** (Must/Should/Could/Won't) ou **RICE** (Reach, Impact, Confidence, Effort).

## 2.2 Spécifications techniques

- Formaliser les exigences **non-fonctionnelles** : performance (temps de réponse cible), disponibilité (SLA visé), scalabilité (nombre d'utilisateurs cible), sécurité.
- Diagrammes utiles : diagramme de séquence, diagramme de cas d'utilisation, et surtout le **modèle C4** (Context, Container, Component, Code) pour documenter l'architecture à différents niveaux de zoom.

## 2.3 Architecture logicielle

- Choix de style : **monolithe** (souvent le bon choix par défaut au démarrage), **monolithe modulaire**, **microservices** (seulement si la complexité organisationnelle le justifie), **serverless**, **event-driven**.
- ⚠️ Ne pas partir sur des microservices "parce que c'est la norme" : ça résout un problème d'échelle organisationnelle, pas un problème technique en soi. Un monolithe bien modularisé scale très loin.
- Patterns d'architecture : **MVC**, **architecture hexagonale / clean architecture** (séparer la logique métier des détails techniques), **CQRS**, **event sourcing** (pour des cas spécifiques, pas par défaut).
- Penser résilience dès la conception : circuit breaker, retry avec backoff, timeout, isolation des pannes (bulkhead).

## 2.4 Choix technologique (stack)

- Critères : maturité de la techno, taille de la communauté, courbe d'apprentissage pour l'équipe, coût (licences, hébergement), écosystème déjà maîtrisé en interne.
- ⚠️ Le piège du "resume-driven development" : choisir une techno parce qu'elle est excitante à apprendre plutôt que parce qu'elle sert le projet.
- Pour un risque technique élevé (fonctionnalité jamais faite dans l'équipe) : faire un **POC (Proof of Concept)** avant de s'engager.
- Documenter chaque choix structurant via un **ADR** (voir 2.8).

## 2.5 Modélisation des données

- SQL : modèle conceptuel puis logique, normalisation (jusqu'à 3NF en général), dénormalisation ciblée seulement si un besoin de perf le justifie.
- NoSQL : modéliser autour des patterns d'accès (query-first design), pas autour des relations.
- Choix SGBD selon le besoin réel : cohérence forte (SQL) vs flexibilité de schéma/scalabilité horizontale (NoSQL) — ce n'est pas un choix idéologique.
- Prévoir dès le départ une stratégie de **migrations de schéma versionnées** (Flyway, Alembic, Prisma Migrate, etc. selon stack).
- Identifier les données sensibles/personnelles dès la conception (RGPD by design) : chiffrement au repos, minimisation de la collecte, durée de rétention définie.

## 2.6 UX/UI Design

- Recherche utilisateur → personas → parcours utilisateur (user journey map).
- Wireframes → maquettes haute-fidélité → prototype interactif (Figma ou équivalent) testable avant dev.
- **Design system** : tokens (couleurs, typographies, espacements), composants réutilisables — évite l'incohérence visuelle et accélère le dev front.
- Tests utilisateurs légers même informels (5 utilisateurs suffisent à détecter la majorité des problèmes d'usabilité).
- Responsive / mobile-first par défaut sauf contexte spécifique.
- Accessibilité (WCAG niveau AA a minima) intégrée dès les maquettes, pas ajoutée après coup.

## 2.7 Sécurité by design

- **Threat modeling** léger (méthode STRIDE : Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege) sur les flux sensibles.
- Principe du **moindre privilège** partout (accès, permissions, API keys).
- Authentification/autorisation : standards éprouvés (OAuth2/OIDC), modèle RBAC (rôles) ou ABAC (attributs) selon la granularité nécessaire.
- Chiffrement en transit (TLS partout) et au repos pour les données sensibles.
- Conformité applicable (RGPD en Europe, éventuellement ISO 27001/SOC2 selon secteur/client).

## 2.8 Architecture Decision Records (ADR)

Documenter chaque décision structurante avec un format court et versionné dans le repo (`/docs/adr/0001-titre.md`) :

```
# ADR 0001 : Titre de la décision

## Statut
Proposé / Accepté / Remplacé par ADR-000X

## Contexte
Quel problème on essaie de résoudre, quelles contraintes.

## Décision
Ce qui a été choisi.

## Conséquences
Ce que ça implique, y compris les compromis acceptés.
```

Utile pour : le choix de stack, le choix d'architecture, tout choix difficile à changer plus tard. Évite de refaire le même débat 6 mois après, et accélère l'onboarding des nouveaux arrivants.

## 2.9 Accessibilité, i18n & performance dès la conception

- Accessibilité : penser navigation clavier, contraste, lecteurs d'écran dès les maquettes.
- Internationalisation (i18n) : externaliser tous les textes dès le départ même si une seule langue est prévue au lancement — très coûteux à ajouter après coup.
- Budget de performance défini en amont (ex : Core Web Vitals cibles pour le web) plutôt que "on optimisera plus tard".

## ✅ Checklist fin de Partie 2

- [ ] User stories rédigées avec critères d'acceptation
- [ ] Architecture choisie et documentée (au moins un ADR)
- [ ] Modèle de données validé, migrations versionnées prévues
- [ ] Maquettes validées par un test utilisateur minimal
- [ ] Menaces sécurité principales identifiées
- [ ] Accessibilité et i18n prises en compte dans les maquettes

> **Retour à l'index :** [README.md](./README.md)
