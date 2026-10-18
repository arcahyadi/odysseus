# Agent OS — Références Maîtres

> **Dossier unique** regroupant les 3 documents fondateurs du projet.
> Tout développement, toute décision, toute migration part de ces 3 fichiers.

---

## 01 — SFD v3.1 (Spécification Fonctionnelle Détaillée)

**Fichier :** `01-SFD-v3.1.md` (~95 KB, 1115 lignes)

Ce que le système **DOIT** faire :
- 25 principes invariants (Constitution, P1-P25)
- 22 modules fonctionnels (§5.1 à §5.22)
- 21 exigences non-fonctionnelles (§6)
- 21 cas d'usage (UC-01 à UC-21)
- Architecture logique 7 couches (§7)
- Feuille de route (§8)

**Nouveau en v3.1 (sept. 2026 — veille) :** P23-P25 (proactivité, grounding, data flywheel) · §5.1.7 Wide Research · §5.11.5 apprentissage depuis les traces · §5.21 ordonnancement proactif/heartbeat · §5.22 grounding & citations · NF-20/NF-21 · UC-20/UC-21.

**Statut :** modules codés → migrés vers OpenCode natif (état réel : `../traceability/TRACEABILITY.md`).

---

## 02 — Analyse Outils Tiers

**Fichier :** `02-OUTILS-TIERS.md` (81 KB)

Ce que le système **PEUT** utiliser :
- 60 outils analysés (Mai-Juin 2026)
- 23 intégrés, 7 patterns absorbés, 6 en veille, 11 en banque, 14 ignorés
- Grille d'évaluation 7 axes (score /35)
- Architecture 5 couches (Connaissance, Exécution, Design, Observabilité, Automation)

**Statut :** Outils clés intégrés (CBM, Graphify, Scrapling, Serena, Kroki, Design Extract...)

---

## 03 — Architecture & Migration

**Fichier :** `03-ARCHITECTURE-MIGRATION.md`

Ce que le système **EST** et **VA DEVENIR** :
- Architecture cible : Odysseus = UI, OpenCode = cœur, Plugins = features SFD
- 7 plugins npm (@agentos/sfd-*)
- 16 agents natifs (.opencode/agents/)
- 2 skills (.opencode/skills/)
- Bridge subprocess/API

**Statut :** Migration terminée, 8 014 lignes supprimées, système opérationnel

---

## Ordre de lecture

1. **03-OBJECTIFS** — Comprendre la vision et l'architecture cible
2. **01-SFD** — Comprendre ce que le système doit faire
3. **02-OUTILS** — Comprendre avec quoi le faire

---

## Documents du dossier

| # | Fichier | Rôle |
|---|---|---|
| 01 | `01-SFD-v3.1.md` | Spécification Fonctionnelle Détaillée (référence) |
| 02 | `02-OUTILS-TIERS.md` | Analyse des 60 outils tiers |
| 03 | `03-ARCHITECTURE-MIGRATION.md` | Architecture cible (Odysseus → OpenCode) — **révisé avec la réalité** |
| 04 | `04-OBJECTIFS-COUVERTURE.md` | Objectifs + **score de couverture mesuré (source unique)** |
| 05 | `05-EVENT-BUS.md` | Bus d'événements (15 familles, 62 types) |
| 06 | `06-ENGINE-OUTILS.md` | Moteur OpenCode + outils par phase |
| 07 | `07-ODYSSEUS-AUDIT.md` | Audit Odysseus — **révisé avec la réalité** |
| 09 | `09-PLAN-ACTIONS-RESTANTES.md` | Backlog priorisé |
| 10 | `10-ARCHITECTURE-MODULAIRE.md` | Analyse combinatoire outils × vision |

> **Retirés le 2026-09-25 (périmés, remplacés par `../traceability/`) :** `08-VERIFICATION-ETAT-ACTUEL.md`, `12-CERTIFICATION-GUIDE-DEV.md`.

---

## Voir aussi (documents dérivés)

Ces documents **partent** des références maîtres et ne les remplacent pas :

- [`../traceability/TRACEABILITY.md`](../traceability/TRACEABILITY.md) — **état réel vérifié** (ce que le code fait vraiment).
- [`../veille/VEILLE-COMPLEMENTAIRE.md`](../veille/VEILLE-COMPLEMENTAIRE.md) — **apports externes** non déjà couverts.
- [`../VISION-INTEGRATION.md`](../VISION-INTEGRATION.md) — **plan unifié** (référence → réel → apports).
- [`../README.md`](../README.md) — **index maître** de toute la documentation.
