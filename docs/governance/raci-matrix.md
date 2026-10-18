# Matrice RACI — Odysseus AgentOS

**Version :** 1.0
**Date :** 2026-08-06

---

## Définition des rôles

| Code | Signification |
|------|--------------|
| **R** | **Responsable** — Exécute la tâche, fait le travail |
| **A** | **Approuveur** *(Accountable)* — Signe le résultat, répond de la qualité. Un seul A par activité |
| **C** | **Consulté** — Donne son avis, ses informations sont nécessaires avant la décision |
| **I** | **Informé** — Reçoit le résultat, tenu au courant après exécution |

---

## Acteurs

| Acteur | Rôle dans Odysseus | Agent OpenCode |
|--------|-------------------|----------------|
| **OpenAgent** | Orchestrateur principal, supervise le pipeline 7 phases | `sfd-orchestrator` |
| **Scout** | Recherche contextuelle, exploration de codebase et documentation | `explore` |
| **OpenCoder** | Exécution : écriture de code, commandes, modifications de fichiers | `executor`, `open-coder` |
| **Planner** | Planification : décomposition en objectifs, estimation, allocation | `planner`, `gsd-planner` |
| **Reviewer** | Qualité : revue de code, lint, analyse statique | `reviewer`, `gsd-verifier` |
| **TestEngineer** | Tests : génération de tests, edge cases | `test-engineer`, `edge-case-gen` |
| **Constitution** | Vérification des 22 invariants de la constitution | `constitution` |
| **SecurityAudit** | Audit de sécurité : STRIDE, OWASP Top 10 | `security-audit` |
| **ContextAgent** | Gestion du contexte projet, compaction, mémoire | `context-agent` |
| **Debugger** | Débogage systématique, isolation de bugs | `gsd-debugger` |
| **Human** | Utilisateur final, administrateur système | — |

---

## Matrice des activités

### Cycle de vie projet

| Activité | OpenAgent | Scout | OpenCoder | Planner | Reviewer | TestEng. | Constitution | SecurityAudit | ContextAgent | Human |
|----------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **Plan** — Définir objectifs, décomposer en tâches, estimer budgets | C | C | I | **R/A** | C | I | I | I | C | I |
| **Build** — Écrire le code, exécuter les commandes, modifier les fichiers | C | C | **R/A** | C | I | I | I | I | I | I |
| **Test** — Exécuter les suites de tests, générer des edge cases | I | I | C | I | C | **R/A** | I | I | I | I |
| **Review** — Revue de code, lint, analyse statique, vérification DoD | C | I | C | I | **R/A** | C | C | C | I | I |
| **Deploy** — Déploiement Docker, mise en production, healthchecks | **R/A** | I | C | I | I | I | I | I | I | C |
| **Monitor** — Supervision, alertes, dashboards, logs | **R/A** | I | I | I | I | I | I | I | I | I |

### Gouvernance et sécurité

| Activité | OpenAgent | Scout | OpenCoder | Planner | Reviewer | TestEng. | Constitution | SecurityAudit | ContextAgent | Human |
|----------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **Classification de risque** — Évaluer le risque d'une requête avant exécution | **R/A** | I | I | I | I | I | C | C | I | C |
| **Vérification constitution** — Vérifier le respect des 22 invariants | C | I | I | I | I | I | **R/A** | C | I | I |
| **Audit sécurité** — STRIDE, OWASP Top 10, scan de vulnérabilités | C | I | I | I | I | I | C | **R/A** | I | C |
| **Budget enforcement** — Vérifier et imposer les limites de tokens/coût | **R/A** | I | I | I | I | I | I | I | I | C |
| **Gestion des kill-switches** — Activer/désactiver les interrupteurs de sécurité | I | I | I | I | I | I | I | I | I | **R/A** |

### Mémoire et apprentissage

| Activité | OpenAgent | Scout | OpenCoder | Planner | Reviewer | TestEng. | Constitution | SecurityAudit | ContextAgent | Human |
|----------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **Extraction de leçons** — Extraire des leçons d'un run (succès ou échec) | **R/A** | C | I | I | C | C | I | I | C | I |
| **Curation mémoire** — Intégrer les leçons dans la base de connaissance | C | I | I | I | I | I | I | I | **R/A** | I |
| **Compaction contexte** — Résumer et condenser l'historique de conversation | I | I | I | I | I | I | I | I | **R/A** | I |
| **Préférences utilisateur** — Persister et appliquer les préférences | C | I | I | I | I | I | I | I | C | **R/A** |

### Résolution d'incidents

| Activité | OpenAgent | Scout | OpenCoder | Planner | Reviewer | TestEng. | Constitution | SecurityAudit | ContextAgent | Human |
|----------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **Détection incident** — Identifier un incident de sécurité ou de performance | **R/A** | I | I | I | I | I | C | C | I | C |
| **Triage SEV1-SEV4** — Classifier la sévérité et déclencher la réponse | I | I | I | I | I | I | I | **R/A** | I | C |
| **Résolution** — Isoler, corriger, vérifier la correction | C | C | **R/A** | C | C | C | I | C | I | C |
| **Post-mortem** — Rédiger le rapport post-incident blameless | I | I | I | I | I | I | C | C | I | **R/A** |

---

## Matrice des phases SFD (7 phases)

| Phase | R (Responsable) | A (Approuveur) | C (Consulté) | I (Informé) |
|-------|-----------------|---------------|--------------|-------------|
| **CLASSIFY** | OpenAgent | Human | SecurityAudit, Constitution | Scout, Planner |
| **KNOW** | Scout | OpenAgent | ContextAgent | Planner, OpenCoder |
| **PLAN** | Planner | OpenAgent | Scout, ContextAgent | OpenCoder, Human |
| **BUILD** | OpenCoder | OpenAgent | Planner, Scout | Reviewer, TestEngineer |
| **QUALITY** | Reviewer + TestEngineer | OpenAgent | SecurityAudit, Constitution | OpenCoder, Human |
| **AUTOEVAL** | OpenAgent | Human | Reviewer | Planner, ContextAgent |
| **MEMORY_OBSERVE** | ContextAgent | OpenAgent | OpenAgent | Human |

---

## Règles de collaboration

1. **Un seul A par activité.** L'Approuveur est responsable en dernier ressort du résultat.
2. **Pas de R sans A.** Tout Responsable a un Approuveur qui valide son travail.
3. **Le Human est toujours A sur les décisions irréversibles** (déploiement, suppression de données, changements de configuration critiques).
4. **OpenAgent est A par défaut** sur les activités du pipeline sauf exception explicite.
5. **Les phases sont séquentielles.** Une phase ne démarre qu'après approbation de la phase précédente.
6. **Escalade.** Si un agent ne peut pas remplir son rôle R, il escalade à l'Approuveur désigné dans la colonne A.
