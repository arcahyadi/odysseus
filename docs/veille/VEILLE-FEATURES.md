# VEILLE — FEATURES CANDIDATES POUR AGENTOS

> **Date :** 2026-09-25 · **Issu de :** `VEILLE-EXTRACTION.md`
> **Rattachement :** modules `docs/master-ref/01-SFD-v3.1.md` (§5.x) + axes `docs/master-ref/04-OBJECTIFS-COUVERTURE.md`
> **Grille :** chaque candidat est noté Impact (1-5), Effort (1-5), Priorité = Impact − Effort pondéré.
> **Rappel de séquence (Constitution)** : `loop manuel → tools → permissions → observations → budgets → tracing → planning → context/memory → compaction → skills/connectors → goal loop → subagents`. On ne saute pas d'étape.

---

## Synthèse

| Catégorie | Nombre | Philosophie |
|---|---:|---|
| ⚡ **Quick wins** | 10 | Effort ≤ 2, débloquent des axes entiers, aucun refactor lourd |
| 🏗️ **Chantiers** | 14 | Effort 3-5, structurants, à séquencer selon la Constitution |
| 🔭 **Veille long terme / Banque** | 9 | Dépendances lourdes ou valeur différée |

**Fil rouge** : la veille pointe trois manques qui reviennent partout — **boucle d'apprentissage fermée**, **découverte dynamique d'outils MCP**, **observabilité du budget**. Le reste est de la consolidation.

---

## ⚡ QUICK WINS (Impact élevé / Effort faible)

| # | Feature | Module SFD | Axe | Impact | Effort | Justification |
|---|---------|-----------|-----|:---:|:---:|---------------|
| QW1 | **Catalogue de skills pré-encodés à chargement obligatoire** — scan des `SKILL.md` avant toute création/exécution | §5.13.5, §5.17 | Axe 7, Axe 2 | 5 | 2 | Spécifié dans la SFD mais non branché. Praticable immédiatement, gain qualité immédiat sur tous les artefacts. Pattern issu de Claude Skills / `agents-best-practices`. |
| QW2 | **Mode local / dégradé explicite** — providers Ollama / llama.cpp de premier rang + doc de bascule | §5.6, NF-06 | Axe 3 | 4 | 2 | `ModelEndpoint` natif existe déjà ; il manque l'exercice réel. Réponse directe au mouvement self-hosted de la veille. |
| QW3 | **Indicateur de budget tokens live dans le cockpit** — brancher CodeBurn sur le chip budget | §5.9, §5.11 | Axe 8, Axe 6 | 4 | 2 | Chip présent, données non injectées (Axe 8 : 30 %). CodeBurn configuré ON peut alimenter. Quick win visuel fort. |
| QW4 | **`AGENTS.md` généré par projet** — rendre le repo compréhensible pour les agents | §5.13 | Axe 2, Axe 7 | 4 | 1 | Pattern @code_simple. Réduit la dérive de contexte et améliore le suivi des conventions par les agents. Trivial à produire. |
| QW5 | **Checklist qualité vibecoding en phase QUALITY** — sécurité, SEO, perf, accessibilité, secrets | §5.10 | Axe 1 | 4 | 2 | Pattern @buildwithmathias + `permission-matrix`. Aujourd'hui batterie partielle ; la checklist ferme le trou « victoire prématurée ». |
| QW6 | **Consolidation du fallback routage** — exposer blacklist/cooldown et rate-limit dans les traces | §5.6, §5.11 | Axe 3 | 3 | 1 | Déjà 80 % implémenté (`ZenRouter`). Il manque la visibilité. Gain de fiabilité à coût quasi nul. |
| QW7 | **Suggestion de connecteurs MCP (v0)** — détecter un service nommé non connecté et proposer | §5.13.4 | Axe 2, Axe 6 | 4 | 2 | Étape minimale avant le registre complet. Débloque NF-16 sans attendre l'écosystème entier. |
| QW8 | **Grounding + citations dans les rapports Deep Research** | §5.11 | Axe 4 | 4 | 2 | Pattern NotebookLM/SurfSense. Renforce le score de fidélité aux sources déjà tracé. |
| QW9 | **Trace viewer / session replay minimal** — rejouer la chaîne d'appels d'une décision (UC-12) | §5.11 | Axe 8 | 4 | 2 | Les traces existent ; il manque la vue. Valide l'auditabilité et le drift scoring. |
| QW10 | **Cron en langage naturel léger (heartbeat v0)** — brief quotidien via APScheduler | §5.5, §5.9 | Axe 6 | 4 | 2 | APScheduler déjà présent (Decision Engine). Pose la brique heartbeat (0 % aujourd'hui). |

---

## 🏗️ CHANTIERS (structurants)

| # | Feature | Module SFD | Axe | Impact | Effort | Justification |
|---|---------|-----------|-----|:---:|:---:|---------------|
| CH1 | **Boucle d'auto-amélioration fermée** — Génération → Réflexion → Curation, skills auto-générés, deltas incrémentaux | §5.2.4, §5.7.7 | Axe 7 | 5 | 5 | **Le plus fort écart de la veille.** Hermes/OpenClaw/Acontext en font leur cœur, AgentOS est à 45 % avec `autoeval.py` OFF. Séparer les rôles, jamais réécrire la base entière. |
| CH2 | **Registre MCP + découverte dynamique complète** — `tool_search`, `search_mcp_registry`, chargement différé | §5.13.2, §5.13.4 | Axe 2 | 5 | 4 | Dépasse le seuil des 15-20 outils sans saturer le contexte. NF-16. Prérequis pour la scalabilité de l'écosystème d'outils. |
| CH3 | **Exécution durable intégrée** — workflows, activités, retry, compensation (saga), approbations longues | §5.5 | Axe 6 | 5 | 4 | Codé dans `saga.py`, non intégré (Axe 6 : 20 %). C'est ce qui rend crédible NF-04 et le rollback. |
| CH4 | **Goal-ancestry live** — mission → objectif → sous-projet → tâche persistés | §5.3 | Axe 6 | 4 | 3 | Tables SQLAlchemy existent, pas créées en live (30 %). Prérequis d'une gouvernance réelle des budgets par objectif. |
| CH5 | **Heartbeat scheduling complet** — planification, reprise, notifications | §5.5, §5.9 | Axe 6 | 4 | 4 | 0 % aujourd'hui. Recoupe les « scheduled workflows » de SurfSense/Manus. Suite de QW10. |
| CH6 | **Système de préférences utilisateur** — comportementales/contextuelles, résolution de conflits, guardrails | §5.15 | Axe 7 | 4 | 3 | Spécifié v3.0, non résumé dans les axes. Débloque NF-18/NF-19. Fort effet perçu côté utilisateur. |
| CH7 | **Recherche de conversations passées** — `conversation_search` + `recent_chats` + signaux linguistiques | §5.16 | Axe 7 | 4 | 3 | Continuité cross-session (NF-15). Fait partie de la proposition « ne jamais redemander » de la SFD. |
| CH8 | **Classification & rétention des données + droit à l'oubli** | §5.19 | Axe 6 | 4 | 3 | 5 niveaux public→protégé, suppression irréversible multi-surfaces. Prérequis de confiance. |
| CH9 | **Visualiseur inline (widgets SVG/HTML)** — arbre de décision de sortie §5.18 | §5.18 | Axe 8 | 4 | 4 | Sortie visuelle = modalité de premier rang (P22, NF-17). Aujourd'hui limité au texte/tableaux. |
| CH10 | **Trinité branchée dans l'UI** — dashboard CBM + Graphify + Obsidian | §5.7, §5.11 | Axe 4 | 4 | 4 | Axe 4 : Trinité UI à 0 %. Graphify et Obsidian sont des MCP non branchés au pipeline. |
| CH11 | **Wide Research contrôlé** — parallélisation uniquement si critère §5.1.2 mesuré | §5.1.2 | Axe 1 | 4 | 4 | Pattern Manus. À activer sous garde-fou : le multiplicateur multi-agent (3-15×) doit rester visible et borné. |
| CH12 | **Budgets granulaires + multiplicateur multi-agent visible** | §5.1.1, §5.9 | Axe 6 | 4 | 3 | `budget_enforcer.py` opérationnel (85 %) mais séparation budget agent-unique / multi-agent non visible. |
| CH13 | **Multi-canal complet via Gateway** — Discord/Telegram actifs + WhatsApp/Slack | §5.8 | Axe 2 | 3 | 4 | Adapters présents mais kill-switchés (80 %). Pattern OpenClaw (50+ canaux) montre la valeur. |
| CH14 | **Cookbook + comparaison aveugle de modèles** | §5.6 | Axe 3 | 3 | 3 | Absorbé d'Odysseus (socle). Améliore la sélection de modèles et la confiance dans le routage. |

---

## 🔭 VEILLE LONG TERME / BANQUE (valeur différée)

| # | Feature | Module SFD | Axe | Impact | Effort | Justification |
|---|---------|-----------|-----|:---:|:---:|---------------|
| LT1 | **Génération média via MCP** (image/vidéo, pattern Higgsfield) pour sorties visuelles avancées | §5.18 | Axe 8 | 3 | 4 | Utile en bout de chaîne, hors cœur « conduite de projet ». Garder en option débrayable. |
| LT2 | **Report & Podcast Generator multi-format** (PDF/DOCX/HTML, podcast multi-voix) | §5.18 | Axe 4 | 3 | 3 | Pattern SurfSense/open-notebook. Enrichit les livrables de recherche. |
| LT3 | **Navigateur autonome visible** (« Manus's computer ») | §5.18 | Axe 8 | 3 | 5 | Fort effet démo, coût d'infra élevé. À réévaluer après CH9. |
| LT4 | **Orchestration multi-agents « équipes » à grande échelle** | §5.1 | Axe 1 | 3 | 5 | P11/NF-10 : uniquement sur preuve. La veille (60 agents, tmux) est une source de patterns, pas une cible. |
| LT5 | **AirLLM / inférence de modèles géants sur petite VRAM** | §5.6 | Axe 3 | 2 | 4 | Réponse au local-first, mais dépendance lourde. Banque tant que le mode local standard suffit. |
| LT6 | **Design system exposé à l'agent via MCP** (pattern Magic UI) | §5.13 | Axe 8 | 3 | 3 | Cohérence UI du cockpit. Après CH9. |
| LT7 | **Canal WhatsApp** (pattern OpenWA/OpenClaw) | §5.8 | Axe 2 | 2 | 4 | Extension de CH13, risque de maintenance. |
| LT8 | **Veille continue automatisée** — digests de l'écosystème agents/modèles (Claw Code, Kimi, Mistral Vibe) | §5.16, §5.5 | Axe 7 | 3 | 3 | Le secteur bouge vite (fuite Claude Code, réimplémentations). Un workflow de veille interne aurait de la valeur. |
| LT9 | **Analytics privacy-first / captcha self-hosted** (Plausible, ALTCHA, Cap) | §5.4 | Axe 5 | 2 | 2 | Uniquement si endpoints publics. Déjà en banque dans la grille. |

---

## 🎯 TOP 10 — LES IDÉES LES PLUS FORTES

> Classement croisé impact projet × alignement avec la thèse SFD × faisabilité.

| Rang | Idée | Origine veille | Pourquoi c'est fort |
|---:|---|---|---|
| 1 | **Boucle d'auto-amélioration fermée** (Génération→Réflexion→Curation + skills auto) | Hermes Agent, OpenClaw, Acontext | Thèse centrale d'AgentOS (Axe 7) ; c'est LE pattern que la veille place en tête et qu'AgentOS n'a pas encore bouclé. |
| 2 | **Découverte dynamique d'outils** : `tool_search` + registre MCP + suggestion de connecteurs | MCP partout, SFD §5.13.4 | Lève le plafond des 15-20 outils et matérialise l'extensibilité « sans friction » (P21/NF-16). |
| 3 | **Catalogue de skills à chargement obligatoire** | Claude Skills, §5.17 | Quick win à très fort levier qualité : contraintes d'environnement que le modèle ignore sinon. |
| 4 | **Exécution durable intégrée** (workflows + saga + approbations longues) | SFD §5.5 (à brancher) | Rend crédibles reprise après panne et rollback ; aujourd'hui codée mais non branchée. |
| 5 | **Observabilité du budget tokens** (CodeBurn → UI, multiplicateur multi-agent visible) | CodeBurn, OmO, veille « tokens » | Adresse le goulot nº1 de l'écosystème et rend la gouvernance lisible (Axe 6/8). |
| 6 | **Mode local / dégradé de premier rang** (Ollama/llama.cpp) | veille homelab, self-hosted | Souveraineté et continuité : NF-06, et répond au mouvement self-hosted dominant. |
| 7 | **Heartbeat & briefs planifiés** (cron NL) | SurfSense, Manus, Hermes | Axe 6 à 0 % : transforme l'assistant ponctuel en agent qui travaille en continu. |
| 8 | **Grounding + citations dans les rapports** | NotebookLM, SurfSense, open-notebook | Qualité et fiabilité des livrables de recherche (Axe 4), facilement mesurable. |
| 9 | **Session replay / auditabilité** | Manus (sessions rejouables), SFD §5.11 | Valide UC-12 et le drift scoring ; les traces existent déjà, il manque la vue. |
| 10 | **Gouvernance des données** : rétention 5 niveaux + droit à l'oubli | SFD §5.19 + veille vie privée | Prérequis de confiance pour un agent à mémoire persistante ; aucune surface ne l'implémente encore. |

---

## Ordre d'exécution recommandé

```
Quick wins (QW1→QW10)  ──►  débloquent la confiance et la visibilité
        │
        ├─► CH1 (auto-amélioration)  ← dépend de QW1 (skills) + QW3/QW6 (tokens/routing)
        ├─► CH2 (découverte MCP)     ← dépend de QW7 (suggest_connectors v0)
        ├─► CH3 (exécution durable)  ← dépend de QW8 (traces) + QW10 (heartbeat v0)
        └─► CH4→CH5 (goal-ancestry, heartbeat) ← dépendent de CH3 + CH12 (budgets)

Long terme : CH6→CH14, puis LT1→LT9 — après stabilisation des précédents.
```

**Règle d'arbitrage** : un chantier ne démarre que si le quick win qui le rend visible (trace, budget, skill) est en place. C'est l'application directe de la séquence de la Constitution (« ne jamais sauter d'étape »).
