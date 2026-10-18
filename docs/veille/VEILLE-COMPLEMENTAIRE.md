# VEILLE — APPORT NET (ce qui complète vraiment la vision)

> **Objet :** parmi les **108 ressources** de la veille (`VEILLE-EXTRACTION.md`), ne garder que celles qui apportent quelque chose **d'important et de non déjà couvert** par notre vision — que ce soit par **son applicatif entier**, **son concept** ou **sa techno**.
> **Référence de couverture existante :** `02-OUTILS-TIERS.md` (60 outils déjà évalués) + `01-SFD-v3.1.md` (25 principes, 22 modules) + `04-OBJECTIFS-COUVERTURE.md` (8 axes).
> **Méthode :** apport-net = veille − (grille 60 ∪ SFD ∪ socle projet). Tout ce qui est déjà intégré, absorbé, en veille, en banque ou spécifié dans la SFD est **exclu** (liste §4).
> **Date :** 2026-09-25.

---

## Règle de tri
Un item est **gardé** s'il apporte au moins une de ces trois choses :
- 🧩 **Applicatif entier** — une application qu'on n'a pas et qui couvre un besoin non couvert ;
- 💡 **Concept / pattern** — une idée d'architecture absente de la SFD/grille ;
- ⚙️ **Techno** — une brique technique (runtime, modèle, protocole) qu'on ne possède pas.

S'il est **redondant** avec un outil de la grille ou **déjà spécifié** dans la SFD → **exclu** (même s'il est intéressant).

---

## 1. 🧩 Applicatifs entiers à garder

| # | Ressource | Apport net vs ce qu'on a déjà | Module SFD | Décision |
|---|---|---|---|---|
| APP1 | **OpenClaw** (ex-Clawdbot) | Agent personnel self-hosted **contrôlant la machine via 50+ canaux** + `MEMORY.md` + skills auto. On a Discord/Telegram kill-switchés et un système de mémoire structuré : OpenClaw apporte le **multi-canal étendu** et le **pattern mémoire-fichier minimal**. | §5.8, §5.15 | **Absorber** (concept multi-canal) — pas de fork |
| APP2 | **Manus** | Agent généraliste qui **livre un résultat fini** avec **Wide Research** (recherches parallèles), **session replay** et **navigateur visible**. On a la recherche (WF4) et les traces, mais ni le replay ni le navigateur visible. | §5.1.2, §5.11, §5.18 | **Absorber** (3 patterns) |
| APP3 | **Magic UI (+ MCP officiel)** | **Serveur MCP qui expose 150+ composants React/Tailwind** à l'agent. On n'a aucun « MCP de design system ». Nouveau pattern : l'UI devient une brique interrogeable par l'agent. | §5.13, §5.18 | **Techno à évaluer** (cockpit) |
| APP4 | **open-notebook** (lfnovo) | NotebookLM self-hosted avec **podcast jusqu'à 4 voix** + REST API. Redondant avec SurfSense **sauf** le podcast multi-intervenants et la simplicité Docker. | §5.18 | **Veille** (redondance partielle) |
| APP5 | **OpenRAG** | Pile RAG complète **ingestion + hybrid search + agents + MCP + Langflow**. On a ChromaDB maison + RRF : apport = **orchestration RAG via MCP/Langflow** (blueprint). | §5.11, §5.13 | **Veille** (blueprint) |
| APP6 | **PrivateGPT** | Couche **API « façon Claude API » au-dessus d'Ollama/llama.cpp/vLLM**. Apport = pattern de **gateway local** pour le mode dégradé. | §5.6, NF-06 | **Absorber** (concept gateway local) |
| APP7 | **DeerFlow 2.0** | Agent **deep-research OSS** (concurrent direct de WF4). Utile comme **référence de comparaison**, pas à intégrer. | §5.16 | **Veille** (concurrent) |

---

## 2. 💡 Concepts / patterns à garder

| # | Concept | Origine veille | Ce que ça ajoute (absent de la SFD/grille) | Module SFD | Décision |
|---|---|---|---|---|---|
| C1 | **Wide Research** (N recherches indépendantes parallèles, bornées) | Manus | La SFD parle de décomposition (§5.1.2) mais **pas** du cas « N agents de recherche parallèles ». Pattern concret, sous garde-fou multiplicateur. | §5.1.2 | **Absorber** |
| C2 | **Session replay / sessions rejouables** | Manus | Les **traces** existent (P15) mais **aucune vue de rejeu**. Rend UC-12 réellement vérifiable. | §5.11 | **Absorber** (quick win) |
| C3 | **Navigateur autonome visible** (« Manus's computer ») | Manus | **Visualisation de l'agent en action**. Absent partout ; fort effet, coût infra. | §5.18 | **Banque** |
| C4 | **Continuité par sessions détachées** (tmux) | @ai.honeycove | Le **palliatif** qui montre le besoin : garder un agent vivant au-delà du client. La couche durable (§5.5) doit le remplacer, pas l'imiter. | §5.5 | **Absorber** (cadrage) |
| C5 | **Grounding + citations** (répondre depuis les sources) | NotebookLM, Deep Research | La SFD a le score de fidélité (§5.11) mais **pas** le pattern « réponse citée, sourcée ». Enrichit WF4. | §5.11, §5.10 | **Absorber** |
| C6 | **Heartbeat / cron en langage naturel / briefs planifiés** | SurfSense, Manus, Hermes | **Aucun module SFD** ne couvre la planification récurrente (Axe 6 : 0 %). Apport net. | §5.5, §5.9 | **Absorber** (chantier) |
| C7 | **`AGENTS.md` généré par projet** (repo compréhensible par l'agent) | @code_simple | Réduit la dérive de contexte ; convention émergente absente du projet. Trivial à produire. | §5.13 | **Absorber** (quick win) |
| C8 | **Multi-canal étendu au-delà Discord/Telegram** (Slack/WhatsApp/Email/CLI via gateway unique) | OpenClaw | La SFD spécifie une gateway mais **2 canaux seulement** sont câblés. Apport = périmètre. | §5.8 | **Absorber** (consolider) |
| C9 | **MCP de composants / de design system** | Magic UI | Pattern « exposer une lib UI comme MCP » — absent. | §5.13, §5.18 | **Absorber** (concept) |
| C10 | **Sous-agents par tâche** (au niveau outil, pas métier) | Mistral Vibe 2.0 | Nuance vs P12 : Vibe découpe **par tâche**, pas par contexte — contre-exemple utile pour trancher. | §5.1.3 | **Veille** |
| C11 | **Data flywheel MLOps** — export des trajectoires de run pour générer des données d'entraînement / RL | **Hermes** (Nous Research) | Nos traces servent à l'**audit**, pas à l'**apprentissage** : aucun module SFD ne transforme les runs en dataset/récompense. Hermes en fait un outil de MLOps. | §5.11, §5.7.7 | **Absorber** (veille long terme) |
| C12 | **Déploiement élastique « idle ≈ gratuit »** — exécution sur Daytona/Modal/Singularity/SSH selon la charge | **Hermes** | La SFD suppose Docker Compose toujours allumé ; pattern d'exécution à la demande (coût nul au repos) absent. | §5.5, NF-06 | **Veille** |

---

## 3. ⚙️ Technos à garder

| # | Techno | Ce que ça ajoute (brique absente) | Module SFD | Décision |
|---|---|---|---|---|
| T1 | **Ollama + llama.cpp** | **Mode local/dégradé de premier rang**. Supporté par Odysseus mais jamais exercé comme chemin nominal → souveraineté + continuité (NF-06). | §5.6 | **Intégrer** (quick win) |
| T2 | **AirLLM** | Faire tenir des **modèles géants sur petite VRAM sans quantisation** — brique Cookbook/optimisation. Dépendance lourde. | §5.6 | **Banque** |
| T3 | **Kimi K2.6** (Moonshot) | **Modèle open-weight MIT, 256k contexte**, fort en code agentique — candidat sérieux du routeur local. | §5.6 | **Veille** |
| T4 | **Claw Code / agentty** (réimplémentations Claude Code) | Signal fort : **agents CLI OSS post-fuite Claude Code**. Fil de veille, pas une brique. | §5.6 | **Veille** |
| T5 | **Cap** (CAPTCHA self-hosted) | Complète ALTCHA (déjà en banque) pour tout endpoint public. | §5.4 | **Banque** |

---

## 4. ❌ Exclu — déjà couvert par la vision (non complémentaire)

Ces ressources sont **intéressantes mais n'ajoutent rien** : déjà intégrées/absorbées/spécifiées/écartées.

| Déjà couvert | Où | Ressources de la veille concernées |
|---|---|---|
| **Trinité connaissance** | grille CORE actif | CBM, Graphify, Obsidian |
| **Web unifié** | grille CORE | Scrapling, Crawl4AI, Browser-Harness |
| **Édition sémantique / LSP** | grille | Serena |
| **DB / diagrammes / tests / API demo** | grille | Supabase, Kroki, Playwright, Faker.js, API Toolkit |
| **Socle harness** | grille + projet | OpenCode, Odysseus, OAC, Paperclip, agents-best-practices |
| **Patterns absorbés** | grille | OmO (routing/fallback), HexStrike (perm/sandbox), vibecode (quality pipeline, phase-lock, débat 5 personas, drift), Caveman, HolyClaude, MVI, Approval Gates |
| **Auto-amélioration / skills-memory** | grille + SFD §5.7.7 | Acontext, Hermes*, skills auto, distillation run→skill |
| **Observabilité tokens** | grille + SFD §5.9/§5.11 | CodeBurn, waste detectors, budget tracking |
| **NotebookLM self-hosted + RAG** | grille veille | SurfSense (report/podcast déjà notés) |
| **Découverte d'outils / registre MCP** | SFD §5.13.4 (spécifié) | `tool_search`, `suggest_connectors`, chargement différé |
| **Skills à chargement obligatoire** | SFD §5.13.5/§5.17 (spécifié) | Claude Skills, catalogue SKILL.md |
| **Exécution durable / saga / approbations longues** | SFD §5.5 (spécifié) | workflows durables |
| **Hybrid search RRF** | projet actif | OpenRAG, SurfSense hybrid search |
| **Multiplicateur multi-agent / anti-context-collapse / data sovereignty / MCP-first** | SFD (principes) | (items de la section D « déjà absorbés ») |
| **Design** | grille | Design Extract, Open Design |
| **n8n** | grille (retiré → Decision Engine) | n8n |
| **Banque déjà actée** | grille banque | ALTCHA, Plausible, anime.js, reactbits, UIverse, Blender MCP, SketchUp MCP, MediaAgent, Design Galleries, ScrapGraphAI, Twenty, Cal.com* |
| **Hors scope** | — | marketing/pub (Arcads, Higgsfield, Meta Ads, TopView), OSINT perso (Maigret, PimEyes…), hardware perso (OpenRGB…), apps grand public, films/jeux/musique/lifestyle |

\* **Hermes** figure en « veille » dans la grille. Son **cœur** (auto-amélioration memory+skills) est déjà couvert via Acontext/SFD §5.7.7, son **cron NL** via C6 et son **multi-canal** via C8. Il n'est donc PAS retenu comme outil, **mais deux angles restent des apports nets** : **C11** (data flywheel MLOps / export trajectoires) et **C12** (déploiement élastique idle≈gratuit). *Cal.com : déjà proche de la banque planification.

---

## 5. Synthèse de l'apport net

| Catégorie | Gardés | Dont « Intégrer » |
|---|---|---|
| 🧩 Applicatifs entiers | 7 | 0 (absorber/veille) |
| 💡 Concepts / patterns | 12 | 0 (absorber) |
| ⚙️ Technos | 5 | **1** (Ollama/llama.cpp) |
| **Total apport net** | **24** | 1 |

> **Sur 108 ressources, seules ~22 apportent vraiment du neuf** — le reste est redondant avec une vision déjà très complète. Les 3 apports les plus structurants : **Wide Research** (C1), **Heartbeat/cron NL** (C6), **Grounding+citations** (C5) — tous les trois **absents de la SFD**.
>
> **Nouveaux entrants Sept. 2026 absents de la grille de juin :** OpenClaw, Manus, Claw Code, Kimi K2.6, DeerFlow 2.0, Magic UI MCP, OpenRAG, open-notebook, PrivateGPT, AirLLM.
