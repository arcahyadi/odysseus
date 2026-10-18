# 📚 Documentation AgentOS — Index maître

> **Point d'entrée unique.** La documentation est organisée autour de **`master-ref/`** (la référence fondatrice) ; tout le reste en dérive ou la prolonge.
> Branche : `feat/inventaire-global-v1`.

---

## 🧭 Ordre de lecture conseillé

1. **`master-ref/`** — *ce que le système DOIT faire* (la référence).
2. **`traceability/`** — *ce qu'il fait réellement* (vérifié).
3. **`veille/`** — *ce qui pourrait le compléter* (apports externes).
4. **`VISION-INTEGRATION.md`** — *le plan unifié* (référence → réel → apports).

---

## 1. 📖 Référence fondatrice — `master-ref/`

Le socle. Toute décision part de ces documents.

| Fichier | Rôle |
|---|---|
| [`master-ref/README.md`](master-ref/README.md) | Présentation des documents fondateurs |
| [`master-ref/01-SFD-v3.1.md`](master-ref/01-SFD-v3.1.md) | **Spécification Fonctionnelle Détaillée v3.1** — 25 principes, 22 modules, 21 UC, 21 NF |
| [`master-ref/02-OUTILS-TIERS.md`](master-ref/02-OUTILS-TIERS.md) | Analyse des 60 outils tiers (grille /35) |
| [`master-ref/03-ARCHITECTURE-MIGRATION.md`](master-ref/03-ARCHITECTURE-MIGRATION.md) | Architecture cible : Odysseus → OpenCode |
| [`master-ref/04-OBJECTIFS-COUVERTURE.md`](master-ref/04-OBJECTIFS-COUVERTURE.md) | Objectifs + 8 axes de couverture |
| [`master-ref/05-EVENT-BUS.md`](master-ref/05-EVENT-BUS.md) | Bus d'événements (15 familles, 62 types) |
| [`master-ref/06-ENGINE-OUTILS.md`](master-ref/06-ENGINE-OUTILS.md) | Moteur OpenCode + outils par phase |
| [`master-ref/07-ODYSSEUS-AUDIT.md`](master-ref/07-ODYSSEUS-AUDIT.md) | Audit Odysseus (garder/élaguer) |
| [`master-ref/09-PLAN-ACTIONS-RESTANTES.md`](master-ref/09-PLAN-ACTIONS-RESTANTES.md) | Backlog priorisé (P0→P3) |
| [`master-ref/10-ARCHITECTURE-MODULAIRE.md`](master-ref/10-ARCHITECTURE-MODULAIRE.md) | Analyse combinatoire outils × vision |

> Les documents `08-VERIFICATION` et `12-CERTIFICATION` ont été **retirés le 2026-09-25** (périmés). L'état réel fait foi dans [`traceability/TRACEABILITY.md`](traceability/TRACEABILITY.md).
| [`master-ref/Guide meilleur pratique de dev/`](master-ref/Guide%20meilleur%20pratique%20de%20dev/) | Guide dev (14 chapitres) |

---

## 2. 🔍 État réel & traçabilité — `traceability/`

Ce que le code fait **vraiment** (vérifié), et les écarts avec la doc.

| Fichier | Rôle |
|---|---|
| [`traceability/TRACEABILITY.md`](traceability/TRACEABILITY.md) | **Document maître** — verdict de réalité |
| [`traceability/00-CODE-INVENTORY.md`](traceability/00-CODE-INVENTORY.md) | Inventaire code (routes, modules, MCP, packages…) |
| [`traceability/01-SFD-TRACEABILITY.md`](traceability/01-SFD-TRACEABILITY.md) | Modules SFD ↔ fichiers + kill-switches |
| [`traceability/02-PRINCIPES-UC.md`](traceability/02-PRINCIPES-UC.md) | Principes P1-P22 + UC vérifiés |
| [`traceability/03-MODULARITE.md`](traceability/03-MODULARITE.md) | Couplages + briques interchangeables |
| [`traceability/04-TESTS-REALITE.md`](traceability/04-TESTS-REALITE.md) | Exécution réelle (env, tests, lint) |

---

## 3. 🔭 Veille & apports — `veille/`

Ce que l'écosystème 2026 apporte et qui **n'est pas déjà couvert**.

| Fichier | Rôle |
|---|---|
| [`veille/VEILLE-EXTRACTION.md`](veille/VEILLE-EXTRACTION.md) | 108 ressources triées + verdict |
| [`veille/VEILLE-FEATURES.md`](veille/VEILLE-FEATURES.md) | 33 features candidates (impact/effort) |
| [`veille/VEILLE-COMPLEMENTAIRE.md`](veille/VEILLE-COMPLEMENTAIRE.md) | **Apport net** (24) vs vision existante |

---

## 4. 🗺️ Plan unifié — `VISION-INTEGRATION.md`

[`VISION-INTEGRATION.md`](VISION-INTEGRATION.md) — rassemble **tous les apports** (fondations + intégrations + modularité + veille) dans un plan séquencé (Sprints 0→5).

---

## 5. 🏗️ Architecture — `adr/`

| Fichier | Rôle |
|---|---|
| [`adr/0001-architecture-decision-record.md`](adr/0001-architecture-decision-record.md) | ADR — format de décision |
| [`adr/0002-sfd-pipeline-7-phases.md`](adr/0002-sfd-pipeline-7-phases.md) | ADR — pipeline 7 phases |

---

## 6. ⚙️ Opérations — `operations/`

| Fichier | Rôle |
|---|---|
| [`operations/setup.md`](operations/setup.md) | Installation, config, déploiement |
| [`operations/backup-restore.md`](operations/backup-restore.md) | Sauvegarde / restauration |
| [`operations/email-outlook.md`](operations/email-outlook.md) | Intégration email/Outlook |
| [`operations/security-ci.md`](operations/security-ci.md) | Sécurité & CI |
| [`operations/runbooks/incident-response.md`](operations/runbooks/incident-response.md) | Runbook incident |

---

## 7. 🏛️ Gouvernance — `governance/`

| Fichier | Rôle |
|---|---|
| [`governance/personas.md`](governance/personas.md) | Personas utilisateurs |
| [`governance/raci-matrix.md`](governance/raci-matrix.md) | Matrice RACI |
| [`governance/risk-register.md`](governance/risk-register.md) | Registre des risques |
| [`governance/bus-factor.md`](governance/bus-factor.md) | Analyse bus factor |
| [`governance/sla.md`](governance/sla.md) | SLA / SLO / SLI |
| [`governance/rfc-template.md`](governance/rfc-template.md) | Template RFC |
| [`governance/post-mortem-template.md`](governance/post-mortem-template.md) | Template post-mortem |
| [`governance/deprecation-policy.md`](governance/deprecation-policy.md) | Politique de dépréciation |

---

## 8. 🎨 Assets — `assets/`

Vidéos de démo (`.webm`), images et landing page (`index.html`).

---

*Hub mis à jour le 2026-09-25 — l'ancien README pointait vers des dossiers inexistants ; cet index reflète l'arborescence réelle.*
