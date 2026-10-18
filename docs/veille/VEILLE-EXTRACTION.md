# VEILLE — EXTRACTION DÉDUPLIQUÉE

> **Date :** 2026-09-25
> **Sources traitées (6) :** `fiches_veille.md`, `veille_extraction.md`, `veille_tiktok_complete.md`,
> `veille_tiktok_dev_groupee.md`, `veille_instagram_dev_groupee.md`, `veille_systemes_ia.md`
> **Croisement :** `docs/master-ref/01-SFD-v3.1.md` (25 principes, 22 modules), `02-OUTILS-TIERS.md` (grille 60 outils), `04-OBJECTIFS-COUVERTURE.md` (8 axes)
> **Périmètre :** on conserve tout ce qui est tech/dev/IA/OSS/homelab/OSINT/agents. On écarte films, séries, anime, jeux, musique, lifestyle, bons plans.

**Échelle de verdict (reprise de la grille `02-OUTILS-TIERS.md`)** :
`Intégrer` (à brancher) · `Absorber pattern` (idée/architecture à réutiliser, pas l'outil) · `Veille` (à suivre, décision différée) · `Banque` (idée future, non prioritaire) · `Ignorer` (hors scope).

**Note de croisement importante** : plusieurs ressources de cette veille sont **déjà dans la grille existante** (`OpenCode`, `Odysseus`, `Hermes`, `SurfSense`, `Crawl4AI`, `Acontext`, `Build Your Own X`, `AutoResearch`, `OmO`, `CodeBurn`, `Design Extract`, `Open Design`, `agents-best-practices`, `vibecode-pro-max-kit`, `Caveman`, `NotebookLM`-famille). Elles sont marquées `[déjà grille]` ci-dessous : le verdict tient compte de l'état d'intégration réel (souvent « configuré (off) » ou « veille »).

---

## 0. Synthèse exécutive

| Constat | Détail |
|---|---|
| **Famille dominante** | Les agents autonomes à **mémoire persistante + skills auto-générés + MCP + multi-canal** (Hermes, OpenClaw, Manus, Acontext). C'est exactement la thèse de SFD v3.1 (§5.7, §5.13, §5.17). |
| **Standard transverse** | **MCP** relie tout l'écosystème 2026 (§5.13.1). Rien à inventer : il faut industrialiser la découverte (registre + suggestion). |
| **Goulot récurrent chez les créateurs** | La **consommation de tokens** (routing, compaction, skills, fallback). Recoupe `CodeBurn`, `OmO`, le « Caveman method ». |
| **Angle mort d'AgentOS vs la veille** | La **boucle d'auto-amélioration fermée réellement branchée** (Hermes) et le **registre/découverte MCP dynamique** (§5.13.4) : la veille en fait son sujet #1, la couverture projet est à 45 % (Axe 7) et 0 % (registre). |
| **Bruit à filtrer** | ~60 % des favoris scannés sont du divertissement ; la génération média/pub (Arcads, Higgsfield, Meta Ads, TopView) est hors périmètre d'un « assistant de conduite de projet ». |
| **Signal OSS à suivre** | Écosystème des agents CLI post-« fuite Claude Code » (Claw Code ~195 k★, agentty…), modèles open-weight pour le routeur local (Kimi K2.6, Mistral Vibe 2.0). |

---

## A. OUTILS & TECHNOS

### A.1 Infrastructure, exécution, web

| # | Nom | Catégorie | Source | Ce que c'est | Verdict |
|---|-----|-----------|--------|--------------|---------|
| A1 | **MCP (Model Context Protocol)** | Standard d'intégration | Toutes sources / `veille_systemes_ia` | Standard ouvert agent↔outils, « fil rouge » de 2026 | **Intégrer** — socle déjà acté §5.13.1 ; reste à câbler registre + suggestion |
| A2 | **tmux** | Terminal / continuité | @ai.honeycove (TikTok) | Multiplexeur qui garde les agents en vie après fermeture du laptop | **Absorber pattern** — continuité longue durée (§5.5 / Axe 6) ; les sessions tmux ad hoc sont un palliatif, la couche durable doit prendre le relais |
| A3 | **Ollama** | Runtime LLM local | @docteur_meta (IG) | Fait tourner un LLM en local sur petite machine | **Intégrer** — mode dégradé NF-06 / Axe 3 ; déjà supporté par le routeur |
| A4 | **llama.cpp** | Runtime LLM local | @docteur_meta (IG) | Inférence locale GGUF légère | **Intégrer** — idem A3, brique du mode dégradé |
| A5 | **AirLLM** | Optimisation inférence | @emiliencorbineau (IG) | Fait tenir des modèles géants (Llama 405B→8 Go, DeepSeek-V3→12 Go, Kimi K3→3,72 Go) sur carte ordinaire **sans quantisation** | **Absorber pattern** — intéressant pour le Cookbook / mode local (§5.6, Axe 3), mais dépendance lourde : banque à court terme |
| A6 | **Crawl4AI** `[déjà grille]` | Scraping web | @thomasbssh1 (TikTok) | Scraping + extraction LLM-ready, 68,3 k★ | **Veille** — déjà en fallback `enabled:false` ; Scrapling reste primaire |
| A7 | **Scrapling** `[déjà grille]` | Scraping web | @githubvault écosystème | Web unifié anti-bot, 63,1 k★ | **Intégrer** — déjà CORE actif (rappel de cohérence) |
| A8 | **Cap** | CAPTCHA self-hosted | @nathan_nrgt (TikTok) | CAPTCHA open source, léger, privacy-first | **Banque** — utile seulement si endpoints publics exposés ; recoupe ALTCHA déjà en banque |
| A9 | **n8n** `[déjà grille]` | Automatisation | @nawraskader (TikTok), @aielyott | Orchestrateur visuel 400+ intégrations | **Veille** — retiré du projet au profit du Decision Engine Python ; reste pertinent comme connecteur externe |
| A10 | **NocoDB** | Base no-code OSS | @nawraskader (TikTok) | Alternative open source à Airtable | **Ignorer** — pas de besoin data-table interne identifié |
| A11 | **Cal.com** | Scheduling OSS | @nawraskader (TikTok) | Alternative open source à Calendly | **Banque** — pourrait nourrir les tâches planifiées/heartbeat (Axe 6) |
| A12 | **Recordly** | Capture écran OSS | @howtowebdev (TikTok) | Enregistreur d'écran OSS (AGPL, ~19 k★), alternative à Screen Studio | **Banque** — production de contenu/veille, pas le cœur agent |
| A13 | **Screen Studio** | Capture écran (payant) | @howtowebdev (TikTok) | Référence payante de Recordly | **Ignorer** — remplacé par Recordly |
| A14 | **Magic UI** (+ MCP officiel) | UI React/Tailwind | @rhinowpia (TikTok) | 150+ composants React/Tailwind animés + serveur MCP | **Banque** — pertinent pour le cockpit/UI (Axe 8) ; pattern « MCP de composants » à retenir |
| A15 | **GSAP** | Animation JS | @rhinowpia (TikTok) | Librairie d'animation web | **Banque** — UI uniquement |
| A16 | **Three.js** | 3D WebGL | @rhinowpia (TikTok) | 3D temps réel navigateur | **Banque** — UI/dataviz uniquement |

### A.2 Génération média & marketing (hors cœur)

| # | Nom | Catégorie | Source | Ce que c'est | Verdict |
|---|-----|-----------|--------|--------------|---------|
| A17 | **Higgsfield MCP** | MCP génération média | @madamet3ch / @aielyott | Serveur MCP hébergé, 30+ modèles image/vidéo sans clé API | **Banque** — utile seulement en sortie visuelle avancée (§5.18) ; hors cœur « conduite de projet » |
| A18 | **Meta Ads MCP** (+ byadsco/meta-ads-mcp, Pipeboard) | MCP marketing | @madamet3ch | Pilote les campagnes Meta depuis un agent | **Ignorer** — métier marketing externe, pas de cas d'usage AgentOS |
| A19 | **Arcads.ai** | Vidéo pub UGC IA | @dryxio.us (IG) | Génération de vidéos publicitaires UGC, 1000+ acteurs IA | **Ignorer** — hors scope |
| A20 | **TopView AI** | Avatar vidéo | @leloup_ia (TikTok) | Site d'avatars/pubs vidéo IA | **Ignorer** — hors scope |
| A21 | **Omma AI** `[déjà grille]` | Web design IA | @splinedesign (TikTok) | Création de sites interactifs | **Ignorer** — déjà jugé « mineur » dans la grille |

### A.3 Open source, vie privée & OSINT

| # | Nom | Catégorie | Source | Ce que c'est | Verdict |
|---|-----|-----------|--------|--------------|---------|
| A22 | **Bitwarden / Vaultwarden / KeePassXC / Proton Pass** | Gestion mots de passe | @sansdependances (TikTok) | Gestionnaires OSS / self-hosted (#degafam) | **Banque** — cohérent avec data sovereignty, mais ce n'est pas une brique de l'agent |
| A23 | **OSINT Framework / OSINT-FR** | Annuaire OSINT | @madameb0nplan (IG) | Annuaires interactifs d'outils OSINT | **Banque** — ressource de veille/sécurité, pas une intégration |
| A24 | **Epieos / Maigret / PimEyes / Have I Been Pwned** | OSINT/identité | @madameb0nplan (IG) | Recherche pseudo, faciale, fuites de données | **Ignorer** — outils d'investigation perso, aucun lien AgentOS |
| A25 | **OpenRGB / FanControl / Bulk Crap Uninstaller / Plexus X** | Maintenance PC | @appleuser46652227 (TikTok) | Contrôle RGB, ventilos, désinstall bloatware | **Ignorer** — hardware perso |
| A26 | **Bring! / Tricount / TimeTree / Cosmonote / Locket / Paired** | Apps grand public | @appsguru.fr (TikTok) | Liste de courses, dépenses, calendrier partagé… | **Ignorer** — hors scope |

### A.4 Divers technos à surveiller

| # | Nom | Catégorie | Source | Ce que c'est | Verdict |
|---|-----|-----------|--------|--------------|---------|
| A27 | **Deerflow 2.0** | Agent de recherche OSS | @qantikstudio (TikTok) | Agent de deep-research open source présenté comme « gratuit » | **Veille** — concurrent fonctionnel de WF4 Recherche ; à évaluer si le Deep Research maison stagne |
| A28 | **Obliteratus** | Abliteration LLM | @renauddekode (TikTok) | Retire les verrous des LLM open-weight (Colab) | **Ignorer** — modifie les modèles, pas les agents ; éthique/scope |
| A29 | **Sites utilitaires divers** (@leloup_ia, @gaetan.sentana, @beasttechx, @setups_ai, @alaaalaff) | Sites/web tools | TikTok | Loaders, spinners, retrait de fond, mockups, CSS tools | **Ignorer** — bruit de favoris, faible signal |

---

## B. AGENTS & SYSTÈMES IA

### B.1 Agents autonomes & personnels (le cœur de la thèse)

| # | Nom | Catégorie | Source | Ce que c'est | Verdict |
|---|-----|-----------|--------|--------------|---------|
| B1 | **Hermes Agent** (Nous Research) `[déjà grille: Veille 16/35]` | Agent autonome auto-améliorant | @feu_seo, @metakaihos, @code_simple | MIT, fév. 2026 : crée ses skills, mémoire persistante, cron NL, sous-agents, MCP, 20+ plateformes, MLOps | **Absorber pattern (prioritaire)** — c'est le modèle de l'Axe 7 (auto-amélioration) ; ingérer la boucle memory+nudges+skills, pas le fork |
| B2 | **OpenClaw** (ex-Clawdbot/Moltbot) | Agent personnel self-hosted | `veille_systemes_ia` | Contrôle l'ordi via 50+ canaux, `MEMORY.md`, skills auto, équipes multi-agents, choix du modèle | **Absorber pattern** — multi-canal (§5.8) + skills auto (§5.17) + expérience `MEMORY.md` |
| B3 | **Manus** (Butterfly Effect, racheté par Meta) | Agent généraliste | `veille_systemes_ia` | Planifie, navigue, exécute, livre un résultat fini ; **Wide Research** parallèle, sessions rejouables, « Manus's computer » | **Absorber pattern** — Wide Research (§5.1.2 parallélisation), session replay (§5.11 audit), navigateur visible (Axe 8) |
| B4 | **Acontext** `[déjà grille: Intégrer P0]` | Skill-as-Memory | Grille + TikToks `@0xloucash`/`@code_simple` | Distille les runs en skills Markdown, self-hosted/cloud | **Intégrer** — dit « P0 » dans la grille ; la veille le confirme (cf. D1) |
| B5 | **A2A / équipes multi-agents** | Orchestration | @adamamira.ia, @ai.honeycove | 60 agents Claude coopératifs « 75 % moins cher », orchestration tmux | **Absorber pattern** — à traiter avec prudence (principe P11/NF-10 : ne pas précipiter le multi-agent) |

### B.2 Assistants de recherche & notes

| # | Nom | Catégorie | Source | Ce que c'est | Verdict |
|---|-----|-----------|--------|--------------|---------|
| B6 | **NotebookLM** (Google) | Recherche groundée | `veille_systemes_ia` | Répond uniquement depuis tes sources, citations ; Audio Overviews, mind maps, 2 M tokens | **Absorber pattern** — grounding + citations + formats de briefing (§5.11, Axe 4) |
| B7 | **Perplexity Deep Research** | Recherche web autonome | `veille_systemes_ia` | Rapport sourcé, le plus rapide/cité | **Veille** — concurrent ; pattern de rapport cité |
| B8 | **ChatGPT Deep Research** (GPT-5.5) | Recherche web autonome | `veille_systemes_ia` | Rapport long (30 min) + version light | **Veille** — concurrent |
| B9 | **Gemini Deep Research** (Gemini 3.1 Pro) | Recherche web autonome | `veille_systemes_ia` | Le plus profond technique/scientifique, plan collaboratif | **Veille** — concurrent |
| B10 | **Grok Deep Research** (xAI) | Recherche web autonome | `veille_systemes_ia` | Concurrent récent | **Veille** — concurrent |
| B11 | **open-notebook** (lfnovo) | NotebookLM self-hosted | `veille_systemes_ia` | 18+ fournisseurs, podcasts 4 voix, REST API, MIT, Docker | **Absorber pattern** — alternative self-hosted ; podcast multi-voix (§5.18) |
| B12 | **SurfSense** `[déjà grille: Veille 23/35]` | NotebookLM self-hosted | `veille_systemes_ia` | 27+ connecteurs, report/podcast/slides, hybrid search, 14,4 k★ | **Veille** — absorber Report + Podcast Generator, pas l'outil entier (déjà jugé) |
| B13 | **OpenRAG** | Pile RAG complète | `veille_systemes_ia` | Ingestion, embeddings, recherche hybride, agents, MCP, Langflow | **Absorber pattern** — recherche hybride RRF (déjà dans Axe 4) ; vérifier non-redondance avec ChromaDB maison |
| B14 | **PrivateGPT** (Zylon) | API IA privée locale | `veille_systemes_ia` | Couche « façon Claude API » sur Ollama/llama.cpp/vLLM | **Absorber pattern** — pattern de gateway local (mode dégradé NF-06) |
| B15 | **LibreNote AI / Open Notebook (PRECONX) / InsightsLM** | NotebookLM-like | `veille_systemes_ia` | Alternatives mineures | **Banque** — redondant avec B11/B12 |

### B.3 Agents de code (terminal & IDE)

> Tableau issu de `veille_systemes_ia` §3 + `fiches_veille`.

| # | Nom | OSS | Point fort | Verdict |
|---|-----|:---:|-----------|---------|
| B16 | **OpenCode** `[déjà projet socle]` | ✅ MIT | 75+ fournisseurs, LSP, le plus étoilé | **Intégrer** — c'est le socle du workspace |
| B17 | **Claude Code** | ❌ | Skills/subagents/MCP profonds | **Absorber pattern** — référence de design des skills/sous-agents |
| B18 | **Codex CLI** | ✅ Apache-2.0 | Intégration OpenAI, multi-tâches | **Veille** — provider alternatif du routeur |
| B19 | **Grok Build** (CLI xAI) | ❌ | Agent terminal Rust (TUI), sous-agents | **Veille** — provider alternatif |
| B20 | **Cursor** | ❌ | IDE IA le plus fluide | **Veille** — hors périmètre runtime |
| B21 | **Gemini CLI** | ✅ Apache-2.0 | Free tier généreux | **Veille** — provider alternatif |
| B22 | **Cline** | ✅ | Agent OSS dans VS Code | **Veille** — écosystème |
| B23 | **Aider** | ✅ | Contrôle git natif | **Veille** — écosystème |
| B24 | **Continue** | ✅ | Auto-hébergé dans l'IDE, local | **Veille** — écosystème |
| B25 | **Windsurf** | ❌ | IDE IA alternatif | **Veille** — écosystème |
| B26 | **Claw Code** (~195 k★) | ✅ | Réimplémentation de Claude Code post-fuite | **Veille** — signal fort de l'écosystème, à réévaluer |
| B27 | **agentty / claw-code-agent** | ✅ | Réimplémentations émergentes | **Veille** — fil de veille « agents CLI » |
| B28 | **Mistral Vibe 2.0** | ❌/part. | Sous-agents par tâche | **Veille** — pattern sous-agents |
| B29 | **Kimi K2.6** (Moonshot AI) | ✅ MIT | 1 T paramètres, 256 k contexte, open-weight, code agentique | **Veille** — candidat modèle du routeur (§5.6) |
| B30 | **Odysseus** `[socle projet]` | ✅ AGPL | Workspace IA self-hosted, Cookbook + Deep Research + Compare | **Intégrer** — déjà la base ; absorber Cookbook/Deep Research/Compare |
| B31 | **Hermes / Nomos / Psyche** (modèles Nous) | ✅ | Modèles ouverts du labo Hermes | **Veille** — providers locaux possibles |
| B32 | **Generic agents** (@code_simple) | — | « Agent IA qui apprend tout seul » | **Absorber pattern** — renforce B1 |
| B33 | **OpenAgentsControl (OAC)** `[déjà grille: socle]` | ✅ MIT | Agents éditables, MVI, approval gates, 11 subagents | **Intégrer** — déjà socle méthodologique |
| B34 | **Paperclip** `[déjà grille: Intégré]` | — | Gouvernance multi-agent, budgets, org chart | **Intégrer** — déjà CORE |

---

## C. REPOS OPEN SOURCE

| # | Nom | Source | Ce que c'est | Verdict |
|---|-----|--------|--------------|---------|
| C1 | **Recordly** (`webadderallorg/recordly`) | @howtowebdev | Enregistreur écran OSS, ~19 k★ | **Banque** — cf. A12 |
| C2 | **Build Your Own X** (~499 k★) `[déjà grille: Banque]` | @clemzou.dev | Corpus de tutoriels (DB, OS, Git, Redis…) pour RAG | **Banque** — déjà documenté `rag/BYOX-README.md` |
| C3 | **AutoResearch** (Karpathy, 83 k★) `[déjà grille: à intégrer]` | Grille | Benchmark automatique d'implémentations | **Intégrer** — Axe 7 / observabilité |
| C4 | **Repo officiel de skills Anthropic** | @henriexploria | Collection de skills officielles Anthropic | **Veille** — matière pour le catalogue de skills (§5.17) |
| C5 | **6 repos Claude Code « qui valent le temps »** | @futurastudi0 | Sélection de repos Claude Code | **Veille** — liste non détaillée dans la source |
| C6 | **10 Claude skills 2026** | @0xloucash | Skills Claude notables | **Veille** — catalogue à comparer avec Acontext/B4 |
| C7 | **10 repos GitHub** | @githubvault | Carrousel (liste illisible dans l'image) | **Veille** — compte à suivre en flux |
| C8 | **Repos « moins de tokens »** | @sabbb.md | Repos d'optimisation de consommation | **Veille** — recoupe le goulot tokens (Axe 6) |
| C9 | **Listes de repos OSS** | @heyanthonycharles, @lutendointech, @howtowebdev | Sélections récurrentes | **Veille** — flux à suivre |
| C10 | **5 widgets FlutterFlow OSS** | @lewismenelaws | Widgets mobiles | **Ignorer** — hors stack |
| C11 | **Design Extract / Open Design** `[déjà grille]` | Grille | Extraction design→code / design systems | **Intégrer (off à activer)** — Couche 3 |
| C12 | **agents-best-practices / vibecode-pro-max-kit / OmO / HexStrike / HolyClaude / Caveman** `[déjà grille: patterns absorbés]` | Grille | Patterns harness, qualité, sécurité, sobriété | **Absorber pattern** — déjà absorbés, à consolider |

> **Note :** plusieurs posts citent des listes de repos **dans l'image** (non lisibles). Ils sont classés « Veille » comme **sources à suivre** plus que comme repos identifiés.

---

## D. PRATIQUES, PATTERNS & MÉTHODES

| # | Pattern | Source | Description | Module SFD / Axe | Verdict |
|---|---------|--------|-------------|------------------|---------|
| D1 | **Boucle d'auto-amélioration fermée** (memory + nudges + skills auto-générés) | Hermes (B1), @feu_seo | L'agent crée/améliore ses propres skills à partir de son expérience | §5.2.4, §5.7.7 / Axe 7 | **Absorber pattern (priorité 1)** |
| D2 | **Skills pré-encodés + chargement obligatoire** | Claude Skills, §5.17 | Scan des `SKILL.md` avant toute création/exécution | §5.13.5, §5.17 | **Intégrer** — déjà spécifié, à brancher |
| D3 | **Distillation run→skill** (Génération→Réflexion→Curation) | Acontext, SFD | Séparer générer / réfléchir / curer | §5.2.4, §5.7.7 / Axe 7 | **Intégrer** — `autoeval.py` existe, OFF |
| D4 | **Phase-locking des permissions** | vibecode-kit | Restrictions d'outils par phase | §5.4.2 / Axe 1 | **Absorber pattern** — déjà absorbé, `PHASE_TRACKER` OFF |
| D5 | **Tiered routing + chaînes de fallback + blacklist/cooldown** | OmO | 70/20/10, bascule sur rate-limit | §5.6 / Axe 3 | **Absorber pattern** — déjà implémenté (ZenRouter) |
| D6 | **Débat 5 personas avant implémentation** | vibecode-kit | Architect, Security, Perf, UX, Devil's Advocate | §5.3.2 / Axe 1 | **Absorber pattern** — déjà absorbé, à activer explicitement |
| D7 | **Drift scoring LOW/MEDIUM/HIGH** | vibecode-kit | Signal de dérive après exécution | §5.11 / Axe 8 | **Absorber pattern** — SSE existe, pas toujours émis |
| D8 | **MVI (Minimal Viable Information)** | OAC | <200 lignes/contexte, −80 % tokens | §5.2.1 / Axe 2 | **Absorber pattern** — déjà absorbé |
| D9 | **Approval Gates** | OAC | Humain approuve avant toute exécution | §5.5.4 / Axe 6 | **Absorber pattern** — déjà absorbé |
| D10 | **Quality pipeline 5 étapes** (self-review→test→review→simplify→git) | vibecode-kit | Enrichit la phase QUALITY | §5.10 / Axe 1 | **Absorber pattern** — déjà absorbé |
| D11 | **Caveman method / sobriété de sortie** | @automatise_avec_igor, grille | Phrases <10 mots, zéro blabla, code>explication | Transversal | **Absorber pattern** — déjà absorbé ; les « 7 hacks tokens » la citent |
| D12 | **Réduction de consommation de tokens** (hacks, méthode « Caveman ») | @automatise_avec_igor | 7 astuces jusqu'à −80 % de conso | §5.9 / Axe 6 | **Absorber pattern** — à fusionner avec le budget-tokens §5.9 |
| D13 | **Wide Research** (recherches parallèles indépendantes) | Manus | Décomposition en sous-problèmes parallèles | §5.1.2 / Axe 1 | **Absorber pattern** — uniquement si critère mesuré |
| D14 | **Session replay / sessions rejouables** | Manus | Rejouer une session d'agent | §5.11 / Axe 8 | **Absorber pattern** — renforce l'auditabilité |
| D15 | **« Manus's computer » — navigateur autonome visible** | Manus | L'utilisateur voit l'agent naviguer | §5.18 / Axe 8 | **Banque** — UI d'agent visible |
| D16 | **Tâches planifiées / briefs quotidiens (heartbeat)** | SurfSense, Manus, Hermes | Workflows cron, digest automatique | §5.5, §5.9 / Axe 6 | **Absorber pattern** — Heartbeat à 0 %, à créer |
| D17 | **Comparaison aveugle de modèles** | Odysseus (Compare) | Side-by-side blind | §5.6 / Axe 3 | **Absorber pattern** — déjà dans la base Odysseus |
| D18 | **Cookbook** (scan hardware → reco modèle) | Odysseus | Recommande un modèle adapté à la VRAM | §5.6 / Axe 3 | **Absorber pattern** — déjà dans la base Odysseus |
| D19 | **Grounding + citations** | NotebookLM, SurfSense | Répond uniquement depuis les sources | §5.11 / Axe 4 | **Absorber pattern** — Axe 4 |
| D20 | **Report Generator / Podcast Generator** | SurfSense, open-notebook | Rapports PDF/DOCX, podcasts multi-voix | §5.18 / Axe 4 | **Banque** — enrichissement sortie |
| D21 | **Hybrid Search (RRF)** | OpenRAG, SurfSense | Sémantique + full-text | §5.11 / Axe 4 | **Absorber pattern** — déjà `RRF hybrid search` en actif |
| D22 | **AGENTS.md — rendre le projet compréhensible aux agents** | @code_simple | Documenter le repo pour les agents | §5.13 / Axe 2 | **Absorber pattern** — quicks win |
| D23 | **LSP + LLM** (édition sémantique) | @code_simple, Serena | Navigation/refactoring par LSP | §5.13 / Axe 2 | **Absorber pattern** — Serena déjà CORE |
| D24 | **Les 4 niveaux pour coder avec l'IA** (échelle de maturité) | @code_simple | De l'autocomplétion à l'agent autonome | Transversal | **Veille** — cadre pédagogique |
| D25 | **Checklist vibecoding avant prod** (20 checks sécurité/SEO/perf/a11y) | @buildwithmathias | Contrôles avant mise en production | §5.10 / Axe 1 | **Absorber pattern** — qualité |
| D26 | **7 checks avant de classer un dossier** | @nathancrq | Rituel de fin de tâche | §5.10 | **Banque** — micro-pattern qualité |
| D27 | **MCP-first** | Toutes sources | Tout service intégré via serveur MCP | §5.13.1 | **Intégrer** — déjà principe |
| D28 | **Multiplicateur de coût multi-agent** | SFD / veille | 3-10× (jusqu'à 15×) de tokens en décomposition | §5.1.1 / NF-10 | **Intégrer** — déjà documenté |
| D29 | **Data sovereignty / self-hosted** | @sansdependances, homelabs | Garder données et modèles chez soi | NF-06, §5.19 | **Intégrer** — déjà thèse projet |
| D30 | **Multi-canal gateway** | OpenClaw, SFD §5.8 | Telegram/Discord/Slack/WhatsApp/Email/CLI | §5.8 / Axe 2 | **Intégrer** — Discord/Telegram déjà présents |
| D31 | **Garde-fous anti-effondrement du contexte** | SFD §5.2.4 + Acontext | Unités atomiques, deltas, rôles séparés | §5.2.4 / Axe 7 | **Intégrer** — déjà spécifié |
| D32 | **Token budget tracking / waste detectors** | CodeBurn `[déjà grille]` | 13 catégories, grades A-F, 0 token | §5.9, §5.11 / Axe 6 | **Intégrer** — configuré ON (P1) |
| D33 | **MCP de composants UI** (pattern Magic UI) | Magic UI | Expose une lib de composants à l'agent via MCP | §5.13 / Axe 8 | **Banque** — pattern pour le design system AgentOS |

---

## E. COMPTES & CRÉATEURS À SUIVRE (sources de veille)

| Plateforme | Compte | Spécialité | Priorité |
|---|---|---|---|
| Instagram | **@dryxio.us** | Outils IA, Claude, gated resources (4+ ressources) | Haute |
| Instagram | **@julien.massey** | Ressources IA (REACT, RAM) | Haute |
| Instagram | **@madameb0nplan** | OSINT, vie privée, IoT | Moyenne |
| Instagram | **@madamet3ch** | MCP, IA marketing | Moyenne |
| Instagram | **@emiliencorbineau** | Optimisation LLM (AirLLM) | Moyenne |
| Instagram | **@buildwithmathias** | Vibecoding / qualité web | Moyenne |
| Instagram | **@logic_builder_24** | Roadmap dev IA | Basse |
| Instagram | **@docteur_meta**, **@kshitiz.kamal** | Homelab, IA locale | Basse |
| Instagram | **@simon_de_lima** | Outils dev (gated) | Basse |
| TikTok | **@rhinowpia** | Claude Code + skills + MCP + UI | Haute |
| TikTok | **@ai.honeycove** | tmux + agents IA, orchestration | Haute |
| TikTok | **@feu_seo** | Hermes Agent, auto-amélioration | Haute |
| TikTok | **@metakaihos** | Claude + Obsidian + NotebookLM + Hermes | Haute |
| TikTok | **@renauddekode** | Modèles open-weight (Kimi, Mistral Vibe), OSS | Haute |
| TikTok | **@code_simple** | LLM, agents, LSP, OSS (très prolifique) | Haute |
| TikTok | **@unefille.ia** | Projets open source (Odysseus, Claude Code free) | Haute |
| TikTok | **@automatise_avec_igor** | Optimisation tokens, ressources Claude | Moyenne |
| TikTok | **@sansdependances** | Dé-googlisation, self-hosted | Moyenne |
| TikTok | **@githubvault** | Repos GitHub en flux | Moyenne |
| TikTok | **@dembstech** | Créateurs FR (Le Dev ULTIME, uxpeak) | Basse |
| TikTok | **@howtowebdev** | Projets OSS (Recordly) | Moyenne |
| TikTok | **@0xloucash**, **@futurastudi0**, **@sabbb.md** | Repos/skills Claude Code | Moyenne |
| TikTok | **@adamamira.ia**, **@sage.ai_** | Orchestration multi-agents | Basse |
| TikTok | **@itstundealao** | « Fact or Hype ? » (anti-hype) | Basse |
| TikTok | **@wellx.tech**, **@quiet_home_rack**, **@stackviking** | Homelab/self-hosting | Basse |
| Hors réseau | **uxpeak** (platform.uxpeak.com), **Le Dev ULTIME** (Teachizy), **@dembstech** | Formation dev FR | Basse |

---

## F. CONTENUS NON PERTINENTS (à ignorer explicitement)

| Catégorie | Volume | Exemples |
|---|---|---|
| Films / séries / anime | ~97 favoris | Irishman, Amsterdam, Hellsing, Kabaneri, Look Back… |
| Jeux vidéo | ~23 | Project Zomboid, Abiotic Factor, Outer Wilds, Pokémon fangame… |
| Musique | ~8 | mix/master, producers, Aina the End… |
| Lifestyle / bons plans | ~170 | @dealabs.com (packs promo), offres étudiants |
| Apps grand public | 6 | Bring!, Tricount, TimeTree, Cosmonote, Locket, Paired |
| Hardware perso | 4 | OpenRGB, FanControl, Bulk Crap Uninstaller, Plexus X |
| OSINT perso | 6 | Epieos, Maigret, PimEyes, HIBP, OSINT Framework, OSINT-FR |
| Génération média/pub | 5 | Arcads.ai, Higgsfield MCP, Meta Ads MCP, TopView AI, Omma AI |
| Sites « perte de temps » | ~12 | @leloup_ia, @gaetan.sentana, @beasttechx, @setups_ai |
| Ressources « gated » marketing | 7 | Posts à mot-clé (OUTILS, REACT, RAM, JOIN, SPEC) |
| JDR / D&D | 1 | Owlbear.rodeo, Watabou, Dice.run |

> **Bruit global** : sur 513 favoris TikTok scanés, seuls **92** sont tech/info (~18 %). La valeur de la veille tient à une poignée de comptes à forte densité (§E), pas au volume.

---

## G. LECTURE CROISÉE — ANGLE MORTS & CONFIRMATIONS

| Sujet de la veille | État AgentOS | Action |
|---|---|---|
| Auto-amélioration fermée (Hermes) | Axe 7 : 45 %, `autoeval.py` OFF | Priorité chantier (§5.7.7) |
| Registre MCP + suggestion de connecteurs dynamique | Axe 2/6 : non implémenté (0 % pour le registre) | Quick win architectural (§5.13.4) |
| Skills pré-encodés à chargement obligatoire | §5.17 spécifié, catalogue non branché | Quick win (§5.13.5) |
| Heartbeat / tâches planifiées | Axe 6 : 0 % | Chantier (§5.5/§5.9) |
| Multi-canal | Discord/Telegram kill-switchés | Consolider (§5.8) |
| Mode local / dégradé | Supporté (ModelEndpoint), peu exercé | Quick win (NF-06) |
| Grounding + citations | Deep Research existe | Consolider (§5.11) |
| Observabilité tokens | CodeBurn ON (P1) | Brancher l'indicateur budget UI (Axe 8) |
| Exécution durable — workflows, retry, reprise | Codés, câblés (P14 PARTIEL) | Intégration à l'auto-éval |
| Exécution durable — saga (compensation) | **Échafaudage câblé, jamais armé** ; l'action n'est pas exécutée | Chantier (§5.5) — non implémenté |
| Goal-ancestry live | Axe 6 : 30 % | Chantier (§5.3) |

---

*Fin de l'inventaire. Voir `VEILLE-FEATURES.md` pour la hiérarchisation impact/effort et le rattachement modules SFD / axes de couverture.*
