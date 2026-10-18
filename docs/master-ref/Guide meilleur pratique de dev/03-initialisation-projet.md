# PARTIE 3 — INITIALISATION DU PROJET (Setup)

## 3.1 Structure du repo

- **Monorepo vs polyrepo** : monorepo simplifie le partage de code et les changements transverses (bon pour petite/moyenne équipe) ; polyrepo isole mieux les équipes autonomes à grande échelle mais complexifie les changements transverses.
- Arborescence type à documenter dès le départ (`src/`, `tests/`, `docs/`, `scripts/`, `infra/`...).
- Conventions de nommage de fichiers/dossiers cohérentes et documentées.

## 3.2 Git workflow

| Stratégie | Contexte idéal |
|---|---|
| Git Flow | Releases planifiées, plusieurs versions en prod en parallèle |
| GitHub Flow | Déploiement continu, une seule version en prod |
| GitLab Flow | Entre les deux, avec branches d'environnement |
| Trunk-based development | Équipe mature, CI/CD solide, forte discipline de tests |

- Protection de branche (`main`) : review obligatoire, CI verte obligatoire avant merge.
- Process de Pull/Merge Request standardisé (template de description, checklist).

## 3.3 Conventions

- **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `perf:`) — permet de générer un changelog automatiquement et de clarifier l'intention de chaque commit.
- Naming conventions de code cohérentes avec les standards du langage/framework utilisé.
- **Semantic Versioning** (MAJOR.MINOR.PATCH) pour tout ce qui est versionné (lib, API, appli).

## 3.4 Environnements

- Typiquement : Dev (local) → Staging/Recette → Pré-prod (optionnel) → Prod.
- Configuration externalisée par environnement (principe **12-factor app** : config dans l'environnement, jamais en dur dans le code).
- 🏢 Environnements éphémères (review apps) générés automatiquement par PR pour valider visuellement avant merge.

## 3.5 CI/CD — mise en place

Pipeline type :

```
Push / PR → Lint → Build → Tests (unit + integration) → Scan sécurité →
   → Déploiement auto (staging) → Tests e2e → Déploiement (prod, manuel ou auto selon contexte)
```

- Quality gates : pas de merge si tests rouges, couverture minimale non respectée, ou vulnérabilité critique détectée.
- Outils courants : GitHub Actions, GitLab CI, CircleCI, Jenkins — le choix compte moins que la discipline de l'utiliser systématiquement.
- Déploiement automatique en staging systématique ; en prod, automatique si l'équipe a la maturité de tests suffisante, sinon validation manuelle explicite.

## 3.6 Linting, formatting, quality gates

- Linter + formatter imposés et automatisés (pas de débat de style en code review).
- **Pre-commit hooks** (Husky, pre-commit framework) pour bloquer les erreurs évidentes avant même le push.
- Analyse statique de code (SonarQube ou équivalent) pour détecter code smells, duplication, complexité excessive.
- Fichier `.editorconfig` pour l'homogénéité cross-IDE.

## 3.7 Gestion des secrets

- ⚠️ Jamais de secret en dur dans le code, même "temporairement" — c'est souvent définitif une fois dans l'historique Git.
- `.env.example` versionné (sans valeurs réelles), `.env` toujours dans `.gitignore`.
- 🏢 Pour une équipe/prod : gestionnaire de secrets dédié (Vault, AWS/GCP Secrets Manager, Doppler...) plutôt que des fichiers `.env` partagés manuellement.
- Rotation régulière des secrets et credentials, surtout après un départ d'équipe ou une fuite suspectée.

## 3.8 Documentation initiale

- `README.md` : objectif du projet, installation, démarrage rapide, structure du repo.
- `CONTRIBUTING.md` : comment contribuer (process de PR, conventions).
- `CHANGELOG.md` (format "Keep a Changelog") — idéalement généré depuis les Conventional Commits.
- `ARCHITECTURE.md` ou dossier `/docs/adr` pour les décisions structurantes.
- `LICENSE` et `CODE_OF_CONDUCT.md` si projet open source.

## 3.9 Outils de gestion de projet

- Choix selon la taille : Trello/GitHub Projects pour petite équipe, Jira/Linear pour équipe moyenne/grande avec besoin de reporting fin.
- Structurer le backlog en hiérarchie claire : Epic > Feature > Story > Task.
- Board avec colonnes explicites (To do / In progress / In review / Done) et limites de WIP si Kanban.

## ✅ Checklist fin de Partie 3

- [ ] Repo initialisé avec structure et conventions documentées
- [ ] Workflow Git choisi et branche `main` protégée
- [ ] Pipeline CI/CD fonctionnel (lint + tests au minimum)
- [ ] Secrets gérés hors du code source
- [ ] README et CONTRIBUTING rédigés
- [ ] Outil de gestion de projet configuré avec backlog initial

> **Retour à l'index :** [README.md](./README.md)
