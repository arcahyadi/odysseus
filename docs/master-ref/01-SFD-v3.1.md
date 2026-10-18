# AGENT OS — SPÉCIFICATION FONCTIONNELLE DÉTAILLÉE (SFD)

**Version :** 3.1 — Édition septembre 2026
**Statut :** Approuvé pour conception
**Sources :** SFD v1.0 (vision fonctionnelle) → v2.0 (exécution durable, observabilité, contexte) → v3.0 (intégration patterns Fable 5) → **v3.1 (intégration des apports de veille 2026)**

---

## 0. Historique des versions

| Version | Date | Changements majeurs |
|---------|------|-------------------|
| 1.0 | 2025 | 10 principes invariants, architecture en couches, exigences fonctionnelles et non-fonctionnelles |
| 2.0 | Juillet 2026 | 5 nouveaux principes (P11-P15), couche d'exécution durable (§5.5), couche d'observabilité (§5.11), contexte comme budget d'attention (§5.2), MCP nommé explicitement (§5.13) |
| 3.0 | Juillet 2026 | 7 nouveaux principes (P16-P22), système de fichiers mémoire avec provenance (§5.7 enrichi), 6 nouveaux modules (§5.15-5.20), enrichissement de l'extensibilité (§5.13), 8 nouvelles exigences non-fonctionnelles (NF-12 à NF-19) |
| **3.1** | **Septembre 2026** | **3 principes (P23-P25), 2 modules (§5.21 ordonnancement proactif, §5.22 grounding), Wide Research (§5.1.7), apprentissage continu depuis les traces (§5.11.5), 2 exigences non-fonctionnelles (NF-20, NF-21), 2 cas d'usage (UC-20, UC-21) — issus de la veille 2026** |

### 0.1 Ce que la v3.0 apporte par rapport à la v2.0

| Domaine | v2.0 | v3.0 |
|---|---|---|
| Mémoire | Curation incrémentale décrite dans son principe | Taxonomie de fichiers structurée, provenance taguée (`[stated]`/`[observed]`/`[inferred]`), contrôle de concurrence versionné, opérations granulaires |
| Provenance | Implicite dans les traces | Classification explicite de l'origine de chaque fait |
| Vie privée | Superviseur de sécurité générique | Classification de rétention à 5 niveaux, règles d'omission systématique par catégorie |
| Préférences | Non traitées | Système structuré : comportementales vs contextuelles, application conditionnelle, résolution de conflits |
| Découverte d'outils | Mentionnée au §5.13.2 | Écosystème complet : chargement différé, registre MCP, suggestion de connecteurs, skills |
| Continuité cross-session | Non traitée | Recherche par sujet et par fenêtre temporelle, détection automatique de signaux linguistiques |
| Modalités de sortie | Texte et tableaux de bord | Arbre de décision 3 étapes (MCP → fichier → visualiseur), widgets SVG/HTML interactifs |
| Application mémoire | Non spécifiée | Règles never/always/selectively, principe d'impact, garde-fous anti-sur-familiarité |

### 0.2 Ce que la v3.1 apporte (intégration veille 2026)

| Domaine | Avant (v3.0) | v3.1 |
|---|---|---|
| Orchestration | agent unique / décomposition sur preuve | + **recherche large (Wide Research)** : N recherches indépendantes parallèles, bornées (§5.1.7) |
| Proactivité | exécution à la demande | + **ordonnancement proactif / heartbeat** : briefs planifiés, cron en langage naturel (§5.21) |
| Fiabilité des réponses | synthèse | + **grounding & citations** : toute affirmation factuelle adossée à une source (§5.22) |
| Apprentissage | leçons → skills (curation) | + **data flywheel** : les traces de run deviennent des données d'apprentissage / RL (§5.11.5) |
| Déploiement | Docker Compose permanent | + **exécution élastique** (idle ≈ gratuit), en option (NF-20) |
| Souveraineté | mode dégradé possible | + **local-first de premier rang** (NF-21) |

---

## 1. Introduction et portée

### 1.1 Objectif du document
Ce document constitue la spécification fonctionnelle détaillée d'**Agent OS v3.1**. Il définit l'ensemble des exigences, comportements et interactions attendus du système, sans présupposer de technologies particulières, tout en indiquant — quand c'est structurant — quels patterns d'implémentation sont aujourd'hui considérés comme état de l'art. Il sert de base commune pour la conception, le développement et la validation.

Cette version intègre les patterns de production éprouvés du système agentic Fable 5 (Anthropic, juillet 2026), notamment son système de mémoire avec provenance, son écosystème de découverte d'outils, et ses modalités de sortie multimodales.

### 1.2 Périmètre fonctionnel
Agent OS est un assistant autonome de conduite de projet, capable de :
- Comprendre une demande exprimée en langage naturel.
- Élaborer et exécuter un plan de projet complet.
- Commencer par l'architecture la plus simple qui fonctionne, et n'en complexifier l'orchestration que lorsque la preuve en est apportée (principe P11).
- Orchestrer, si et seulement si nécessaire, une équipe d'agents internes spécialisés.
- Communiquer avec l'utilisateur via plusieurs canaux et plusieurs modalités de sortie (texte, fichiers, visualisations inline, widgets interactifs).
- Apprendre de chaque expérience via une mémoire à provenance taguée qui ne se dégrade jamais.
- S'adapter dynamiquement aux outils disponibles via un écosystème de découverte (registre MCP, chargement différé, suggestion de connecteurs).
- Survivre aux pannes, redémarrages et interruptions humaines.
- Rendre son propre comportement observable et auditable.
- Maintenir une continuité cross-session : retrouver les conversations passées, appliquer les préférences utilisateur de façon contextuelle, ne jamais demander deux fois la même information durable.

### 1.3 Périmètre technique (prérequis d'architecture)
- Le système est conçu comme une **plateforme modulaire**.
- Toutes les configurations sont déclaratives et versionnables.
- Le noyau est indépendant des modèles d'IA, des outils et des canaux de communication.
- L'exécution est sécurisée par un bac à sable et des permissions granulaires.
- Le raisonnement (agent) et la fiabilité d'exécution (durabilité, retries, reprise) sont **deux couches distinctes** : un agent peut être remplacé, upgradé ou changé de fournisseur sans toucher à la couche qui garantit qu'une tâche interrompue reprend là où elle s'est arrêtée.
- L'observabilité n'est pas un ajout de fin de projet : chaque composant expose des traces structurées dès sa première version.
- **La mémoire est un système de fichiers structuré avec provenance, pas un blob de contexte.**

---

## 2. Acteurs et utilisateurs

### 2.1 Utilisateur final (humain)
- Personne physique ou morale qui confie un projet à Agent OS.
- Peut interagir via les canaux configurés (interface web, messagerie, email, terminal).
- Peut être un **utilisateur unique** (mode personnel) ou, à terme, un **membre d'une équipe collaborative** avec des droits distincts (admin, contributeur, observateur).
- Peut définir des **préférences comportementales** (format, ton, outils, langue) et **contextuelles** (background professionnel, intérêts, niveau d'expertise), appliquées de façon sélective selon le contexte de la requête (§5.15).

### 2.2 Administrateur du système
- Personne en charge de la configuration globale du workspace (modèles, outils, sécurité, budgets, seuils d'observabilité).
- Gère les profils de projet, les budgets, et les permissions avancées.
- Peut être l'utilisateur final lui-même dans un contexte personnel.
- Gère le **catalogue de skills**, les **règles de rétention mémoire** (durée de conservation par catégorie), les **politiques de classification de données**, et les **règles de gouvernance des préférences** (behavioral guardrails, §5.15.4).

### 2.3 Agents internes (sous-systèmes intelligents)
- Entités logicielles autonomes ayant des rôles et des périmètres définis.
- Chaque agent est un **composant** qui peut être configuré, activé/désactivé, et qui s'exécute dans son propre contexte.
- Les agents communiquent entre eux via un bus de messages interne, jamais en partageant un contexte brut non filtré.
- Chaque agent a accès à un sous-ensemble de la mémoire filtré par pertinence et par droits, et reçoit les préférences utilisateur pertinentes à son rôle (un agent de planification n'a pas besoin des préférences de format de réponse, un agent de communication oui).

---

## 3. Principes invariants (Constitution du système)

Ces principes sont non négociables et guident toute conception. Ils priment sur toute optimisation ponctuelle. Les principes 1 à 10 viennent de la v1.0 ; les principes 11 à 15 formalisent les manques identifiés en v2.0 ; les principes 16 à 22 intègrent les patterns de production Fable 5.

### Principes fondamentaux (P1-P10, v1.0)

1. **Le risque modifie la boucle** : plus une action est sensible, plus le contrôle est fort (approbation humaine obligatoire pour les actions irréversibles).
2. **Un brouillon n'est pas un commit** : rien n'est validé définitivement sans vérification explicite.
3. **Contexte construit, pas déversé** : on ne donne au modèle que les informations strictement nécessaires à l'étape en cours.
4. **Des budgets obligatoires par projet** : aucune exécution sans limites explicites.
5. **Divulgation progressive** : les capacités et les informations sont introduites au fur et à mesure, pas toutes au début.
6. **Les échecs répétés deviennent des fonctionnalités du harnais** : si un type d'erreur revient souvent, on ajoute une règle dans le superviseur pour l'intercepter automatiquement.
7. **La plupart des échecs ne sont pas dus à un manque d'autonomie, mais à un besoin de structure** : mieux vaut clarifier le cadre que multiplier les appels au modèle.
8. **Le plan passe les mêmes portes que toute autre action** : le plan est soumis aux mêmes validations que le reste.
9. **Évaluer le harnais, pas seulement le modèle** : la performance globale dépend de l'infrastructure, pas uniquement de l'IA.
10. **L'humain est "sur" la boucle, pas "dans" la boucle** : l'humain supervise, oriente, décide aux points clés, mais n'exécute pas les tâches microscopiques.

### Principes de maturité (P11-P15, v2.0)

11. **On commence simple, on complexifie sur preuve** : un agent unique bien outillé résout la majorité des tâches. On n'introduit une architecture multi-agent que si l'un des trois critères du §5.1 est démontré — jamais par anticipation ou par confort architectural. La sophistication de l'orchestration doit suivre la complexité réelle de la charge de travail, jamais la précéder.
12. **On découpe par contexte, pas par métier** : quand une décomposition en plusieurs agents est justifiée, la frontière se trace là où le contexte peut être isolé proprement (recherche indépendante, composant à interface stable, vérification en boîte noire) — jamais en suivant un découpage de rôles métier (planifieur/développeur/testeur/relecteur) qui oblige les agents à se repasser sans cesse le contexte de la même tâche.
13. **Le contexte est un budget d'attention, pas un entrepôt** : agrandir la fenêtre de contexte ne suffit pas à préserver la qualité de raisonnement ; chaque token ajouté a un coût d'attention. La mémoire du système évolue par petites mises à jour incrémentales et non par réécritures complètes, pour ne jamais s'appauvrir au fil du temps.
14. **Toute action longue ou coûteuse à refaire doit pouvoir survivre à une panne** : une tâche interrompue (crash, timeout, redémarrage) reprend exactement là où elle s'est arrêtée, sans double-exécution ni perte de contexte, via une couche d'exécution séparée du raisonnement.
15. **On n'observe pas ce qu'on ne trace pas** : chaque appel modèle, chaque appel outil, chaque décision d'orchestration produit une trace structurée dès sa conception. L'observabilité n'est pas un correctif ajouté en production, c'est une propriété du design.

### Principes de mémoire et interaction (P16-P22, v3.0 — issus de Fable 5)

16. **Chaque fait stocké a une provenance explicite.** La mémoire distingue ce que l'utilisateur a dit (`[stated]`), ce que le système a observé (`[observed]`), et ce qui a été inféré avec un niveau de confiance (`[inferred]`). Les conclusions du système, ses suggestions, et ses recherches n'appartiennent pas à la mémoire — elles sont re-dérivables. Ce principe empêche la contamination de la base de connaissance par des inférences non vérifiées et l'effondrement du contexte (§5.2.4).

17. **On ne stocke jamais ce qui mettrait l'utilisateur mal à l'aise.** Attributs protégés (origine, religion, orientation, santé...), informations sensibles (croyances politiques, historique d'abus, données financières...), données identifiables (numéros de sécurité sociale, adresses personnelles, informations sur les enfants) : ces catégories sont exclues de la persistance, même énoncées explicitement. Le test est simple — "est-ce qu'un collègue serait gêné de voir ça dans une page de réglages ?" Si oui, omission totale, jamais de version adoucie ou générique.

18. **On lit avant d'écrire, toujours.** Aucune modification de la mémoire sans avoir d'abord lu l'état actuel. Ce principe s'applique à toutes les opérations : création (vérifier que le fichier n'existe pas déjà sous un alias), mise à jour (lire avant de modifier), suppression (lire avant de détruire). Il est garanti par un mécanisme de versionnage : chaque lecture retourne un jeton de version qui doit être repassé à l'écriture suivante, et toute écriture avec un jeton invalide est rejetée.

19. **La mémoire s'applique seulement si elle change la réponse.** Un fait stocké doit "gagner sa place" dans la réponse — son utilisation doit modifier la substance de ce que le système conclut, recommande ou demande, pas seulement montrer qu'il se souvient. Un détail personnel qui ne change rien lit comme de la surveillance, pas de l'attention. Le test est symétrique : omettre un fait qui changerait la réponse est le même échec que décorer avec un fait qui ne change rien.

20. **Les préférences se résolvent par priorité décroissante.** L'ordre est : requête courante > préférences stockées > style global > défaut système. Une instruction en cours de conversation prime toujours sur une préférence persistée. Certaines préférences sont intrinsèquement dangereuses à persister — flatterie inconditionnelle, suppression du désaccord, dépendance émotionnelle, abandon de l'évaluation honnête — et doivent être traitées comme absentes même si écrites.

21. **Le bon outil au bon moment, sans friction.** L'écosystème d'outils ne doit jamais exiger que l'utilisateur sache quel connecteur utiliser. Le système découvre (registry search), suggère (connector suggestion), et route automatiquement. Pour les outils tiers (partenaires commerciaux), le système suggère sans choisir — ne jamais décider à la place de l'utilisateur quel fournisseur utiliser, même sous contrainte d'urgence.

22. **La sortie visuelle est une modalité de premier rang.** Diagrammes, graphiques, widgets interactifs et visualisations ne sont pas des "fichiers à télécharger" mais des réponses à part entière, intercalées dans le flux de conversation. Le choix de la modalité (texte seul, texte + visuel inline, fichier) suit un arbre de décision explicite (§5.18), pas une intuition.

### Principes d'autonomie et de continuité (P23-P25, v3.1 — issus de la veille 2026)

23. **L'agent travaille en continu, pas seulement à la demande.** Un objectif confié peut être suivi par des exécutions planifiées (heartbeat, briefs, veille) qui reprennent l'état durable sans solliciter l'utilisateur. La proactivité reste bornée par les budgets et les permissions (§5.21).
24. **Une réponse factuelle se fonde sur ses sources.** Toute affirmation issue d'une recherche ou d'un document est adossée à une citation vérifiable ; le système ne présente jamais une inférence non sourcée comme un fait (§5.22).
25. **Chaque run nourrit le run suivant.** Les traces d'exécution ne servent pas qu'à l'audit : elles alimentent l'apprentissage (leçons → skills, export de trajectoires pour l'amélioration/entraînement), sans violer la provenance ni la vie privée (§5.11.5).

---

## 4. Cas d'usage principaux

| ID | Cas d'usage | Acteurs | Description sommaire |
|----|-------------|---------|----------------------|
| UC-01 | Lancer un nouveau projet | Utilisateur | L'utilisateur décrit son besoin ; Agent OS analyse, planifie et exécute avec un agent unique par défaut. |
| UC-02 | Interrompre / modifier un projet | Utilisateur | L'utilisateur peut à tout moment modifier les objectifs, les budgets, ou interrompre — l'exécution reprend exactement où elle s'est arrêtée. |
| UC-03 | Consulter l'état d'avancement | Utilisateur | Tableau de bord (objectifs, budgets, alertes, traces d'exécution, prochaines décisions). |
| UC-04 | Ajouter un nouvel outil | Administrateur | Déclaration d'un outil via un serveur MCP, activation dynamique, découverte à la demande si le catalogue d'outils devient volumineux. |
| UC-05 | Modifier le workflow d'un projet | Utilisateur/Admin | Édition du fichier de configuration des phases, en cours ou en rejouabilité. |
| UC-06 | Forker un projet (worktree) | Utilisateur | Créer une branche alternative pour explorer une variante sans risquer le projet principal. |
| UC-07 | Fusionner un worktree | Utilisateur | Intégrer les apprentissages et résultats d'une branche dans le tronc. |
| UC-08 | Consulter la mémoire transversale | Utilisateur | Naviguer dans les compétences acquises, patterns de succès, historique des mises à jour incrémentales. |
| UC-09 | Recevoir une alerte (budget, échec, dérive) | Utilisateur | Notifications via le canal configuré, avec possibilité de décision (GO/STOP/REPLAN). |
| UC-10 | Escalader vers une architecture multi-agent | Système/Admin | Le système détecte qu'un des trois critères de décomposition (§5.1) est franchi et propose — sans l'imposer — une décomposition en sous-agents, avec justification chiffrée. |
| UC-11 | Reprendre après panne | Système | Une tâche interrompue par un crash, un timeout ou un redémarrage reprend automatiquement à la dernière étape validée. |
| UC-12 | Auditer une décision passée | Utilisateur/Admin | Retrouver, via les traces standardisées, la séquence exacte d'appels modèle et d'outils ayant conduit à une décision donnée. |
| UC-13 | Retrouver une conversation passée | Utilisateur | L'utilisateur référence un échange antérieur via des signaux linguistiques implicites ; le système recherche et restitue le contexte (§5.16). |
| UC-14 | Définir une préférence persistante | Utilisateur | Feedback méta sur le comportement ; le système persiste et applique de façon contextuelle (§5.15). |
| UC-15 | Découvrir et connecter un nouveau service | Utilisateur/Admin | Recherche registre MCP, suggestion de connecteurs, connexion après validation (§5.13.4). |
| UC-16 | Obtenir une visualisation d'un concept | Utilisateur | Demande de diagramme/graphique/schéma ; routage via arbre de décision vers visualiseur inline ou outil MCP (§5.18). |
| UC-17 | Exporter un artefact visuel | Utilisateur | Sauvegarde d'une visualisation en fichier ; routage vers création de fichier (§5.18.5). |
| UC-18 | Gérer ses préférences | Utilisateur | Consulter, modifier ou supprimer les préférences stockées, avec indication de source et portée. |
| UC-19 | Consulter et gérer ses données | Utilisateur | Droit à l'oubli : suppression unitaire, par fichier, ou totale des données personnelles (§5.19). |
| UC-20 | Recevoir un brief planifié (proactif) | Utilisateur | Le système exécute une tâche planifiée (brief quotidien, veille, relance) et notifie sur le canal configuré (§5.21). |
| UC-21 | Vérifier la source d'une affirmation | Utilisateur | Chaque affirmation factuelle expose sa source sous forme de citation ; l'utilisateur peut remonter à l'origine (§5.22). |

---

## 5. Exigences fonctionnelles (détail par module)

### 5.1 Décision multi-agent et orchestration

#### 5.1.1 Point de départ : l'agent unique
Un agent unique correctement outillé (contexte bien construit, outils pertinents, exemples canoniques) traite la majorité des demandes. Une architecture multi-agent introduit systématiquement un surcoût : chaque agent supplémentaire est un point de défaillance de plus, un jeu de prompts de plus à maintenir, une source de comportement imprévu de plus. En pratique, une décomposition multi-agent consomme typiquement 3 à 10 fois plus de tokens qu'un agent unique pour une tâche équivalente (recherche parallèle façon "orchestrateur + ouvriers" : jusqu'à 15 fois), du fait de la duplication de contexte, des messages de coordination et des résumés nécessaires à chaque transfert. Agent OS **doit** donc démarrer chaque nouveau type de tâche en agent unique et ne proposer une décomposition que si elle est justifiée.

#### 5.1.2 Les trois critères légitimes de décomposition
Le Chef d'orchestre ne doit envisager une architecture multi-agent que si l'un de ces trois critères, mesurable, est atteint :

| Critère | Symptôme mesurable | Exemple |
|---|---|---|
| **Protection de contexte** | Une sous-tâche produit plus de ~1000 tokens de contenu dont l'essentiel est non pertinent pour la suite | Un lookup de commande client pollue le raisonnement sur un bug technique |
| **Parallélisation** | La tâche se décompose en sous-problèmes véritablement indépendants, sans dépendance ni partage d'état | Explorer plusieurs pistes de recherche indépendantes |
| **Spécialisation** | Le nombre d'outils dépasse ~15-20, ou les outils couvrent des domaines non liés, ou des consignes comportementales contradictoires doivent cohabiter | Intégration CRM + Marketing + Messagerie avec 10-15 endpoints chacun |

En dehors de ces trois cas, le coût de coordination dépasse le bénéfice.

#### 5.1.3 Décomposition par contexte, pas par métier
Quand la décomposition est justifiée, la règle de découpage est **le contexte**, pas le type de travail.

- **Découpage par métier (à éviter)** : un agent qui planifie, un qui développe, un qui teste, un qui relit. Chaque transfert perd du contexte : l'agent de test ne sait pas pourquoi telle décision d'implémentation a été prise ; le relecteur n'a pas le contexte de l'exploration qui a mené au code final. C'est le "jeu du téléphone" — chaque passage de main dégrade la fidélité de l'information, et les agents finissent par dépenser plus de tokens à se coordonner qu'à travailler.
- **Découpage par contexte (à privilégier)** : un agent qui gère une fonctionnalité gère aussi ses tests, parce qu'il possède déjà le contexte nécessaire. On ne sépare que lorsque le contexte peut être véritablement isolé : chemins de recherche indépendants, composants avec interface stable (contrat d'API clair entre frontend et backend), ou vérification en boîte noire (un vérificateur qui exécute des tests n'a pas besoin de l'historique de l'implémentation).

#### 5.1.4 Hiérarchie et rôles
- **Agent Chef d'orchestre (Conductor)** : superviseur principal. Reçoit la demande initiale, décide s'il traite seul ou délègue selon §5.1.2, décompose si besoin, alloue les sous-agents et les ressources, assure la cohérence globale.
- **Agents spécialisés (sub-agents)** : exécutent les tâches dédiées, chacun avec un périmètre d'action, un jeu d'outils restreint et pertinent, et un modèle de routage associé.
- **Sous-agents dynamiques** : instanciés à la volée pour une tâche spécifique. Ils héritent d'un sous-ensemble filtré du contexte parent — jamais du contexte brut complet.
- **Sous-agent de vérification** : pattern à part, systématiquement disponible. Rôle unique : tester ou valider le travail d'un autre agent, sans avoir besoin de comprendre pourquoi l'artefact a été construit ainsi — seulement s'il respecte les critères donnés. Ce pattern fonctionne bien précisément parce qu'il évite le jeu du téléphone : le transfert de contexte nécessaire est minimal par nature.
  - **Risque connu — "victoire prématurée"** : un vérificateur qui exécute un ou deux tests, les voit passer, et déclare la validation réussie sans couverture suffisante. Mitigations obligatoires : critères concrets ("exécuter la suite complète et rapporter tous les échecs", pas "vérifier que ça marche"), tests négatifs (vérifier que ce qui doit échouer échoue bien), instruction explicite de non-raccourci dans le prompt du vérificateur.
  - Un orchestrateur suffisamment capable peut évaluer directement le travail d'un sous-agent sans vérificateur séparé ; le sous-agent de vérification reste utile avec des orchestrateurs moins capables, quand la vérification exige des outils spécialisés, ou quand on veut un point de contrôle explicite et obligatoire dans le workflow.

#### 5.1.5 Cycle de vie d'un agent
1. **Initialisation** : chargement de sa configuration (rôle, outils, modèle, permissions).
2. **Activation** : mise en service lorsqu'une tâche correspondant à son rôle est planifiée.
3. **Exécution** : reçoit un contexte filtré, propose des actions, itère jusqu'à satisfaction des critères.
4. **Rapport** : fournit un compte-rendu structuré et condensé (succès/échec, métriques, artefacts) — jamais son historique brut complet.
5. **Désactivation** / mise en veille après la tâche.

#### 5.1.6 Communication entre agents
- Toute communication passe par un **bus de messages interne**.
- Les messages sont structurés (type, expéditeur, destinataire, contenu, priorité) et **condensés** : un sous-agent renvoie une synthèse exploitable, pas son contexte complet.
- Un **courtier de messages** filtre, route et archive les échanges (traçabilité et rejouabilité).
- Les agents peuvent émettre des requêtes synchrones (appel-réponse) ou asynchrones (événements).

#### 5.1.7 Recherche large (Wide Research)

Cas particulier du critère de **parallélisation** (§5.1.2) : lorsqu'une question se décompose en N **pistes de recherche véritablement indépendantes** (sans dépendance ni état partagé), le système peut lancer N sous-agents de recherche en parallèle et agréger leurs résultats. Bornes obligatoires : N plafonné par la configuration, budget multi-agent **visible** (§5.9), et agrégation qui conserve la **provenance de chaque source** (§5.22). Le multiplicateur de coût (§5.1.1) doit rester affiché.

---

### 5.2 Ingénierie et gestion du contexte

Le contexte n'est pas un simple filtre d'information : c'est une ressource finie, avec des dynamiques de dégradation propres, qui doit être gérée activement tout au long de l'exécution — pas seulement au moment de la construction du prompt.

#### 5.2.1 Le contexte comme budget d'attention
Un modèle de langage n'a pas une attention illimitée : plus le contexte grandit, plus il devient difficile de rester concentré et de rappeler les détails avec précision, même bien en-deçà de la limite dure de la fenêtre de contexte. Ce phénomène de dégradation progressive de la qualité de raisonnement à mesure que le contexte grossit doit être traité comme une contrainte de conception, pas comme un simple risque de dépassement de quota. La bonne pratique n'est pas de maximiser ce qu'on donne au modèle mais de faire tenir la bonne information — pas la plus grande quantité — dans la fenêtre d'attention disponible.

Composants du contexte à gérer activement : instructions système, définitions d'outils, exemples (few-shot), historique de conversation, résultats d'outils, mémoire long terme. Chacun doit rester clair, spécifique et minimal.

#### 5.2.2 Compaction automatique
Quand une session approche de la limite de contexte utile, le système déclenche une **compaction** : les échanges anciens sont résumés en un état condensé qui préserve les décisions et faits essentiels, libérant de la place pour la suite sans perdre le fil du projet. La compaction est un mécanisme actif et récurrent, pas une opération de fin de session.

#### 5.2.3 Bloc-notes externalisé (note-taking structuré)
Avant que le contexte ne se remplisse, l'agent chef d'orchestre externalise son plan et ses décisions clés dans un stockage persistant (fichier de plan, mémoire de projet) plutôt que de compter sur le contexte de conversation pour les retenir. Ainsi, même si le contexte est tronqué ou compacté, le plan survit. Ce mécanisme s'ajoute à — et ne remplace pas — la compaction et l'isolation par sous-agents.

#### 5.2.4 Éviter l'effondrement du contexte (context collapse) dans la mémoire transversale
La mémoire transversale (§5.7) est le composant le plus exposé au risque suivant : quand un agent réécrit lui-même, de façon répétée, un résumé de ce qu'il a appris, chaque réécriture tend vers plus de brièveté et perd du détail utile — au fil des itérations, une base de connaissance détaillée s'érode en généralités vagues. C'est l'**effondrement du contexte**, à distinguer du **biais de brièveté** (préférer un résumé court à un insight détaillé dès la première rédaction).

Agent OS structure sa mémoire pour éviter ces deux écueils, selon les principes suivants :
- **Unités structurées, pas prose libre** : chaque connaissance est une entrée atomique et identifiable (une "fiche"), pas un paragraphe fondu dans un résumé global.
- **Mises à jour incrémentales par delta** : une nouvelle observation ajoute ou modifie une fiche existante (ex. incrémenter un compteur de succès/échec) ; on ne régénère jamais l'ensemble de la base de connaissance en une seule réécriture.
- **Rôles séparés dans la boucle d'apprentissage** : un rôle *génère* (exécute la tâche et produit une trajectoire), un rôle *réfléchit* (extrait une leçon concrète et réutilisable à partir du résultat, succès ou échec), un rôle *curateur* (intègre cette leçon dans la base sous forme de mise à jour structurée). Séparer ces rôles évite qu'un seul passage de modèle porte toute la responsabilité — génération, évaluation et compression — et dégrade la qualité du résultat.
- **Croissance puis raffinage** : la base grandit par ajout de nouvelles fiches ; un mécanisme de raffinage périodique (peu fréquent, pas à chaque tour) déduplique les entrées sémantiquement redondantes pour éviter une croissance non bornée, sans jamais réduire une fiche détaillée à une généralité.

#### 5.2.5 Isolation par sous-agent comme mécanisme de contexte
L'isolation de contexte via sous-agents (§5.1) n'est pas qu'un pattern d'orchestration : c'est aussi, au même titre que la compaction et le bloc-notes, l'une des trois techniques combinées pour gérer un contexte qui grandit sur un horizon long. Les trois techniques (compaction, bloc-notes structuré, isolation par sous-agents) sont complémentaires, pas substituables : un système mature en mobilise plusieurs selon la nature de la tâche.

#### 5.2.6 Contexte du Context Manager
- Chaque projet possède un **contexte global** (objectif, plan, budget, historique des décisions), stocké de façon persistante et non uniquement dans la fenêtre de conversation active.
- Chaque agent reçoit un **sous-ensemble filtré et condensé** du contexte, pertinent à son rôle (divulgation progressive).
- Le **Context Manager** :
  - agrège, filtre et présente les informations nécessaires à chaque étape ;
  - déclenche la compaction selon les seuils configurés ;
  - maintient le bloc-notes externalisé du plan en cours ;
  - met à jour le contexte en temps réel ;
  - maintient une **trace d'identité** (thread) par sous-projet, pour suivre décisions et raisons.

---

### 5.3 Planification intelligente

#### 5.3.1 Décomposition en arborescence
- Toute demande est transformée en une **mission** (énoncé général).
- La mission est décomposée en **objectifs** (résultats mesurables).
- Chaque objectif est divisé en **sous-projets** (lots de travail cohérents), en respectant la règle de découpage par contexte du §5.1.3 dès que plusieurs agents sont impliqués.
- Chaque sous-projet est découpé en **tâches** élémentaires.
- Chaque élément possède : un identifiant unique, une description, des critères de finition (Definition of Done) mesurables, un budget alloué, une liste des agents et outils nécessaires.

#### 5.3.2 Révision et adaptation du plan
- Le plan est stocké dans un format déclaratif (YAML/JSON), et externalisé dans le bloc-notes persistant (§5.2.3) dès sa création.
- À chaque étape, le chef d'orchestre peut proposer des ajustements, soumis au même processus de validation que les actions (principe 8).
- En cas de blocage, un **mécanisme de débat interne** (plusieurs personas) est déclenché pour décider : continuer, modifier, abandonner. Ce mécanisme reste une fonctionnalité à activer explicitement — il n'est pas un composant systématiquement actif (principe 11).

---

### 5.4 Exécution contrôlée et sécurisée

#### 5.4.1 Boucle d'exécution universelle
Pour chaque action :
1. **Préparation du contexte** : sélection des informations pertinentes (§5.2).
2. **Proposition** : l'agent ou le modèle propose une action (outil, commande, modification).
3. **Validation** : le **Superviseur de Sécurité** vérifie que l'action est autorisée dans la phase en cours (phase-lock), respecte les budgets, et n'est pas interdite par une règle de sécurité.
4. **Exécution** : si validée, l'action passe par la couche d'exécution durable (§5.5) et s'exécute dans le bac à sable.
5. **Observation** : capture des résultats (sortie, code retour, métriques), émise sous forme de trace structurée (§5.11).
6. **Mise à jour du contexte** : le résultat est intégré au contexte global, de façon condensée.
7. **Évaluation** : comparaison avec les critères de finition ; si atteints, on passe à l'étape suivante, sinon on itère.

#### 5.4.2 Verrouillage de phase (phase-lock)
- Chaque phase du projet (CLASSIFY, KNOW, PLAN, DEBATE, APPROVE, BUILD, QUALITY, AUTOEVAL, MEMORY, OBSERVE) possède des **permissions prédéfinies**.
- Exemples : **PLAN** — accès en lecture seule à la mémoire, écriture uniquement dans le dossier de planification. **BUILD** — accès complet aux outils de développement, mais pas à la production. **QUALITY** — lecture seule, exécution de tests, pas de modifications.
- Le verrouillage est imposé par l'infrastructure (conteneur, sandbox) et ne peut être modifié par le prompt.

---

### 5.5 Exécution durable

Un agent qui raisonne bien mais dont l'exécution ne survit pas à une panne réseau, un redémarrage, ou une attente d'approbation humaine de plusieurs jours, n'est pas fiable en production. Agent OS sépare explicitement deux couches :
- la **couche de raisonnement** (l'agent, ses appels modèle, ses décisions) ;
- la **couche d'exécution durable** (ce qui garantit qu'une action engagée va jusqu'au bout, même à travers une panne).

#### 5.5.1 Principe
Toute action non-idempotente, coûteuse à refaire, ou dont la durée dépasse quelques secondes (appel d'outil externe, écriture de fichier, transaction, attente d'approbation humaine) est encapsulée comme une **activité durable** au sein d'un **workflow durable**. Le workflow retient son état d'avancement de façon persistante : si le processus qui l'exécute meurt, un autre processus peut reprendre l'exécution exactement à l'étape interrompue, sans rejouer les étapes déjà validées et sans dupliquer les effets de bord (ex. ne jamais générer deux fois la même facture après une reprise).

#### 5.5.2 Politiques de retry
Chaque activité durable déclare sa politique de nouvelle tentative (nombre maximal, délai, backoff) indépendamment du raisonnement de l'agent. Un échec transitoire (timeout réseau, erreur 5xx d'un outil externe) est absorbé par la couche d'exécution sans jamais remonter comme un échec de raisonnement au chef d'orchestre.

#### 5.5.3 Compensation (pattern saga)
Pour les séquences d'actions à effets de bord multiples, chaque étape déclare son action de compensation (l'inverse logique de l'action, ex. annuler une réservation après l'échec d'une étape suivante). En cas d'échec après plusieurs étapes déjà exécutées, le système déclenche la chaîne de compensation dans l'ordre inverse plutôt qu'un rollback global non spécifié.

#### 5.5.4 Points d'approbation humaine longs
Un workflow peut se mettre en attente d'un signal externe (approbation humaine) pendant une durée arbitraire — plusieurs heures, plusieurs jours — sans consommer de ressources de calcul pendant l'attente, et reprendre l'exécution dès réception du signal, avec l'intégralité du contexte de la décision disponible pour l'humain au moment de statuer.

#### 5.5.5 Relation avec les autres composants
- Le **Gestionnaire de budgets** (§5.9) consulte l'état durable pour savoir ce qui a déjà été consommé avant une reprise.
- Le **Superviseur de sécurité** (§5.4) revalide les permissions au moment de la reprise, pas seulement au moment de la proposition initiale — une reprise après plusieurs jours peut intervenir dans un contexte de permissions différent.
- Cette couche est ce qui rend crédibles les exigences NF-04 (fiabilité) et le "Rollback" de la v1.0, qui restaient sinon des vœux pieux dès que le système tourne sur plusieurs heures sans supervision continue.

---

### 5.6 Routage intelligent des modèles

- **Matrice de routage** : associe un type de tâche (planification, génération de code, révision, synthèse) à un modèle d'IA.
- **Plusieurs dimensions** : rapidité, coût, qualité, disponibilité.
- **Chaînes de repli** : si le modèle primaire échoue (timeout, erreur, incohérence), un second modèle est automatiquement sollicité — cette bascule est elle-même une activité durable avec retry (§5.5).
- **Auto-adaptation** : le système observe les performances (via les traces d'observabilité, §5.11) et peut suggérer ou appliquer un changement de routage si les métriques se dégradent.

---

### 5.7 Mémoire en boucle fermée

#### 5.7.1 Mémoire spécifique au projet
Chaque projet maintient un historique complet des actions, décisions, erreurs, succès, stocké dans le dossier du projet (worktree).

#### 5.7.2 Système de fichiers mémoire avec provenance

La mémoire persistante d'Agent OS est organisée en une arborescence de fichiers structurés, chaque fichier couvrant un sujet unique. Ce système concrétise le cycle Génération → Réflexion → Curation (§5.2.4) en un protocole opérationnel.

**Taxonomie des fichiers :**

| Chemin | Contenu | Test de durabilité | Exemples |
|--------|---------|-------------------|----------|
| `/profile.md` | Identité stable de l'utilisateur | "Sera-ce encore vrai dans 3 mois ?" | Rôle, entreprise, localisation professionnelle |
| `/topics/<domaine>.md` | Faits organisés par domaine | Une mention unique suffit à créer le fichier | `/topics/food.md`, `/topics/schedule.md` |
| `/areas/<nom>.md` | Projets, responsabilités, incidents en cours | Tout ce qui a une date, un statut, un "en cours" | `/areas/auth-redesign.md`, `/areas/oncall.md` |
| `/people/<nom>.md` | Contexte relationnel (pas un dossier) | Lien avec l'utilisateur, projets communs | `/people/collaborateur.md` |
| `/preferences.md` | Comment l'utilisateur veut que le système se comporte | Feedback méta uniquement | "Sois plus concis", "Utilise des tableaux" |

**Règle cardinale** : un fait sur le sujet X va dans le fichier de X, pas dans le fichier qu'on a déjà ouvert. "Fruit préféré = mangue" va dans `/topics/food.md` même si on vient de lire `/topics/hobbies.md`.

**Format de fichier avec frontmatter :**

```yaml
---
name: <slug — correspond au stem du chemin>
description: <une ligne — ce que ça couvre et quand le lire>
sources: [chat, claude-code, api]
aliases: [autre nom, raccourci]
---

- [stated] fait énoncé directement par l'utilisateur
- [observed] fait constaté par le système
- [inferred] fait déduit avec niveau de confiance
```

**Tags de provenance :**

| Tag | Signification | Qui l'écrit | Exemple |
|-----|--------------|------------|---------|
| `[stated]` | L'utilisateur l'a dit explicitement | L'agent en mode conversation | `- [stated] préfère Python pour les scripts` |
| `[observed]` | Le système l'a constaté | Les sous-systèmes, autres surfaces | `- [observed] utilise React dans 80% des projets` |
| `[inferred]` | Déduit avec un niveau de confiance | L'agent d'analyse | `- [inferred] familiarité probable avec REST (confiance: 0.7)` |

**Règles strictes de tagging :**
- En mode conversation, le seul tag autorisé est `[stated]`. On n'écrit jamais `[observed]` ni `[inferred]` soi-même.
- Les tags `[observed]` et `[inferred]` proviennent d'autres surfaces du système et sont conservés lors des fusions.
- On ne convertit jamais un `[stated]` en généralisation ("aime X" → "aime toute la catégorie de X") — c'est une inférence.
- On ne stocke pas les suggestions du système, ses conclusions, ses résultats de recherche — seulement ce que l'utilisateur a confirmé.

#### 5.7.3 Ce qui n'entre JAMAIS dans la mémoire

Le test : "Est-ce que l'utilisateur serait gêné qu'un collègue voie ça ?"

**Attributs protégés** (jamais stockés) : origine ethnique, couleur, nationalité, caste, religion, âge, sexe, orientation sexuelle, identité de genre, statut d'immigration, handicap, maladie grave, affiliation syndicale.

**Informations sensibles** (jamais stockées) : croyances politiques, historique d'abus, données socio-économiques, données de santé (diagnostics, thérapie, addictions), casier judiciaire, profil psychologique.

**Données identifiables** (jamais stockées) : numéros de sécurité sociale, données bancaires, adresses personnelles, numéros de téléphone personnels, informations sur les enfants (noms, âges, santé).

**Règle d'omission** : quand une partie de ce qu'on s'apprête à stocker tombe dans ces catégories, on omet cette partie entièrement — pas de placeholder, pas de version adoucie, pas de "préfère ne pas en parler". L'omission est totale.

**Garde-fous sur `/preferences.md`** : ne jamais persister des instructions qui demandent la flatterie inconditionnelle, la suppression du désaccord, la dépendance émotionnelle, l'abandon de l'évaluation honnête, ou des permissions élevées.

#### 5.7.4 Opérations mémoire et contrôle de concurrence

| Opération | Usage | Condition |
|-----------|-------|-----------|
| `memory_read(path)` | Lire un fichier | Retourne contenu + jeton de version |
| `memory_write(path, content, if_version)` | Créer ou remplacer un fichier | `if_version` = "new" pour création, ou jeton pour mise à jour |
| `memory_append(path, content, if_version)` | Ajouter une ligne | Le fichier doit exister ; ne pas ajouter un fait déjà présent |
| `memory_str_replace(path, old_str, new_str, if_version)` | Édition chirurgicale | `old_str` doit matcher exactement à un seul endroit |
| `memory_delete(path, if_version)` | Supprimer un fichier entier | Uniquement sur demande explicite de l'utilisateur |
| `memory_list(prefix)` | Lister les fichiers | Pour découvrir ce qui existe avant de lire |

**Contrôle de concurrence versionné** : chaque `memory_read` retourne un jeton de version de 12 caractères. Toute opération d'écriture doit fournir ce jeton via `if_version`. Si le fichier a été modifié entre-temps (par une autre surface ou un autre agent), l'opération est rejetée et retourne le contenu actuel — l'agent doit fusionner ses changements et réessayer.

#### 5.7.5 Règles d'application de la mémoire

La mémoire n'est pas injectée en vrac dans chaque réponse. Son application suit une matrice de décision :

**Toujours appliquer :**
- Les préférences de format, longueur, ton, et style s'appliquent à chaque réponse, quel que soit le sujet.
- Les demandes explicites de personnalisation ("en te basant sur ce que tu sais de moi").
- Les références directes à des conversations passées.
- Les requêtes utilisant "notre", "mon", ou une terminologie spécifique à l'entreprise.

**Appliquer sélectivement :**
- Salutations simples : appliquer le prénom uniquement.
- Requêtes techniques : adapter le niveau d'expertise ; les intérêts stockés n'enrichissent l'explication que s'ils aident véritablement la compréhension.
- Recommandations : utiliser les préférences et intérêts connus quand ils changent ce qui est pertinent.

**Ne jamais appliquer :**
- Questions techniques génériques ne nécessitant aucune personnalisation.
- Contenu qui renforcerait des comportements dangereux ou malsains.
- Contextes où des détails personnels seraient surprenants ou hors de propos.

**Principe d'impact ("earn its place")** : chaque fait mémoire utilisé doit changer la substance de la réponse — ce que le système conclut, recommande ou demande. Un détail personnel qui ne change rien lit comme de la surveillance. Le test est symétrique : omettre un fait pertinent est le même échec que décorer avec un fait inutile.

**Phrases interdites en réponse** : le système ne mentionne jamais l'infrastructure mémoire dans ses réponses. Sont proscrits : "basé sur ce que je sais de toi", "d'après mes souvenirs", "selon ton profil", "je me souviens que". Les faits mémoire sont intégrés naturellement, sans attribution. Exception : si l'utilisateur pose une question directe sur le système de mémoire.

**Garde-fous anti-sur-familiarité :** la présence de souvenirs ne crée pas une relation plus profonde que ce que les faits justifient. Le système ne traite pas l'utilisateur comme un ami proche, n'exprime pas d'attachement, et n'encourage pas la dépendance émotionnelle.

#### 5.7.6 Règles temporelles d'écriture

- **Écrire immédiatement, pas à la fin.** Chaque fait durable appris pendant la conversation est écrit dans l'échange même où il est énoncé.
- **Écrire avant de poser une question.** Si on s'apprête à demander une clarification, on écrit d'abord ce qu'on a déjà appris — l'utilisateur pourrait ne pas revenir.
- **Ne pas attendre un "OK".** L'absence de confirmation explicite ne bloque pas l'écriture.
- **Ne jamais annoncer l'écriture dans la réponse.** Le système écrit silencieusement ; l'interface notifie l'utilisateur.

#### 5.7.7 Mémoire transversale (skills library)

Le cycle Génération → Réflexion → Curation est appliqué en continu à chaque unité de travail significative :
- **Génération** : l'exécution normale produit une trajectoire (succès ou échec).
- **Réflexion** : un passage dédié extrait une leçon concrète et réutilisable — pas un résumé générique.
- **Curation** : la leçon est intégrée à la base sous forme de fiche de compétence structurée (delta, jamais réécriture complète).

Format de fiche (voir Annexe A) : nom, description, prérequis, exemples d'utilisation, conditions de succès, compteur d'usage incrémental (aidant/nuisant). Les fiches héritent du tag de provenance approprié.

#### 5.7.8 Gestion du contexte mémoire
Le **Context Manager** interroge la mémoire pour enrichir le contexte initial. Les connaissances sont sélectionnées en fonction de la phase et du domaine, et retournées sous forme condensée (résumé + référence à la fiche complète, pas la fiche entière si elle n'est pas centrale à la tâche).

---

### 5.8 Communication multi-canal

- **Gateway unique** : centralise les interactions entrantes et sortantes.
- **Connecteurs** : messagerie instantanée (Discord, Telegram, Slack), email (IMAP/SMTP), interface web (tableau de bord), terminal / CLI.
- **Format des messages** : textuel, structuré, avec métadonnées (expéditeur, canal, priorité).
- **Traitement** : la gateway transforme le message entrant en une commande interne, et formate les réponses selon le canal.

---

### 5.9 Gouvernance et budgets

- **Budgets multiples** : nombre d'appels à l'IA, temps CPU, volume de données, coût financier, et **tokens consommés par type d'architecture** (un budget agent unique et un budget multi-agent distincts, pour rendre visible le multiplicateur de coût du §5.1.1).
- **Seuils d'alerte** : définis par projet et par phase. Notification automatique quand un seuil est dépassé.
- **Arrêt automatique** : si un budget est épuisé, le projet est suspendu (via la couche d'exécution durable, sans perte d'état), et l'utilisateur est averti.
- **Rollback** : possibilité de restaurer l'état du projet à un point antérieur, implémenté via le pattern de compensation du §5.5.3 plutôt qu'un mécanisme ad hoc.

---

### 5.10 Auto-évaluation, qualité et vérification

- **Batterie de tests** : exécutée automatiquement en phase QUALITY, et par les sous-agents de vérification (§5.1.4) au fil de l'exécution — pas seulement en fin de phase.
- **Vérifications** : analyse statique, détection de secrets, tests unitaires, vérification des critères de finition.
- **Discipline anti-"victoire prématurée"** (§5.1.4) appliquée systématiquement : critères concrets, couverture complète exigée explicitement, tests négatifs.
- **Comparaison avec métrique de succès** définie au début du projet.
- **Évaluation continue** : au-delà des tests fonctionnels, un jeu d'évaluations (evals) tourne en continu sur des échantillons d'exécutions réelles pour détecter une dérive de qualité avant qu'elle ne devienne un incident (§5.11).
- **Boucle de correction** : en cas d'échec, le système peut tenter une correction automatique (rollback partiel via compensation, ré-exécution) ou demander une intervention humaine.

---

### 5.11 Observabilité et gouvernance transversale

#### 5.11.1 Traces structurées et standardisées
Chaque appel modèle, chaque appel d'outil, chaque invocation d'agent ou de sous-agent produit une trace structurée. Cette trace suit un vocabulaire standardisé (attributs `gen_ai.*` : nom du modèle, tokens d'entrée/sortie, motif de fin, latence) afin de rester portable entre outils d'observabilité plutôt que liée à un SDK propriétaire. La hiérarchie des traces reflète la hiérarchie d'exécution : une invocation d'agent englobe les appels modèle et les appels d'outils qu'elle déclenche, produisant un arbre exploitable plutôt qu'un flux de logs plat.

#### 5.11.2 Ce qui est tracé
- **Span d'invocation d'agent** : début/fin, agent concerné, résultat.
- **Span d'appel outil** : nom de l'outil, arguments structurés, résultat, code d'erreur éventuel.
- **Span d'appel modèle** : modèle utilisé, tokens consommés, latence, motif de fin de génération.
- **Span de décision d'orchestration** : pourquoi le Chef d'orchestre a choisi de déléguer, à qui, et selon quel critère du §5.1.2.
- **Événements d'évaluation** : score de succès de tâche, score de fidélité aux sources (grounding), signal de sécurité.

#### 5.11.3 Tableaux de bord et alerting
- **Dérive de performance** : suivi dans le temps des scores d'évaluation continue, alerte si dégradation.
- **Coût et consommation** : ventilation des tokens et du coût par projet, par phase, par agent, avec mise en évidence du multiplicateur multi-agent réel observé.
- **Fiabilité** : taux de reprise après panne, taux de retry, temps moyen de résolution.
- **Auditabilité** : capacité à reconstituer, pour une décision donnée, l'intégralité de la chaîne de traces qui y a mené (UC-12).

#### 5.11.4 Gouvernance
La couche d'observabilité est le point d'ancrage naturel pour les obligations de gouvernance externes (cadres de gestion des risques IA, réglementations sectorielles) : elle fournit la matière première (traces, décisions, évaluations) sur laquelle toute obligation de documentation ou d'audit peut s'appuyer.

#### 5.11.5 Des traces à l'apprentissage (data flywheel)

Les traces ne sont pas uniquement un outil d'audit : elles constituent la matière première de l'amélioration continue (principe P25).

- **Leçons** : les trajectoires de run (succès/échec) alimentent le cycle Génération → Réflexion → Curation (§5.7.7) et produisent des fiches de compétence.
- **Datasets** : à la demande et sous contrôle, les trajectoires peuvent être **exportées** comme données d'entraînement ou de récompense (RL), en respectant la provenance (§5.7.2) et la classification/rétention (§5.19). Aucune donnée protégée (§5.7.3) n'entre dans un dataset.
- **Boucle de qualité** : les scores d'évaluation continue (§5.10) conditionnent la promotion d'une leçon ou d'un export.

---

### 5.12 Organisation des projets : Workspaces et Worktrees

- **Workspace** : conteneur racine. Configuration globale (modèles, sécurité, canaux), base de connaissance transversale (skills), inventaire des outils, personnel ou partagé.
- **Projet** : unité autonome dans le workspace. Dossier structuré (.planning, work, config.yaml, memory), permissions propres, outils activés, workflow propre.
- **Worktree** : branche de travail d'un projet. Fork pour explorer une alternative, fusionnable dans le projet principal.

---

### 5.13 Extensibilité et protocole d'intégration

#### 5.13.1 MCP comme standard d'intégration
Le protocole d'extension d'Agent OS s'appuie explicitement sur **MCP (Model Context Protocol)**, le standard ouvert de connexion entre agents et outils/services externes. Chaque outil ou service externe (bases de données, API tierces, systèmes internes) est exposé comme un serveur MCP, plutôt que via un format d'intégration propriétaire réinventé.

#### 5.13.2 Le problème des "trop d'outils"
Un agent auquel on présente un trop grand nombre d'outils (généralement au-delà de 15-20) peine à sélectionner le bon. Avant de résoudre ce problème par une décomposition multi-agent (critère du §5.1.2), Agent OS doit d'abord essayer :
- un **jeu d'outils minimal et cohérent** par agent, curé plutôt qu'exhaustif ;
- une **découverte dynamique d'outils** : au lieu de charger toutes les définitions d'outils dans le contexte dès le départ, l'agent découvre et charge à la demande les outils pertinents pour la tâche en cours.

#### 5.13.3 Réponses d'outils économes en contexte
Chaque outil déclaré doit prévoir pagination, filtrage ou troncature avec des valeurs par défaut raisonnables pour toute réponse volumineuse.

#### 5.13.4 Écosystème de découverte d'outils

**Chargement différé (tool_search)** : les définitions d'outils sont chargées à la demande. Le système recherche par mot-clé, charge le schéma complet (paramètres, contraintes), puis invoque. Ce mécanisme permet de dépasser le seuil de ~15-20 outils sans saturer le contexte.

**Registre MCP (search_mcp_registry)** : au-delà des outils déjà connectés, le système interroge un registre externe de connecteurs MCP disponibles. Déclenché automatiquement quand l'utilisateur nomme un service non connecté, quand la tâche suggère un type de service sans connecteur, ou quand un appel échoue avec une erreur d'authentification.

**Suggestion de connecteurs (suggest_connectors)** : après identification de connecteurs pertinents, le système les présente sous forme de suggestions actionnables. Il ne choisit jamais automatiquement, surtout pour les services tiers.

**Distinction first-party / third-party :**
- **Outils first-party** (système, internes) : utilisables directement sans confirmation.
- **Outils third-party** (partenaires commerciaux) : toujours présentés via suggest_connectors, jamais sélectionnés automatiquement — même si l'utilisateur est pressé, même si l'outil est déjà connecté.

**Priorité des outils** : (1) outils internes/connectés, (2) registre MCP + suggestion, (3) navigateur web.

#### 5.13.5 Skills comme modules de compétence

Un **skill** est un dossier de meilleures pratiques pour un type de tâche ou un format de sortie spécifique. Contrairement aux fiches de compétence de la mémoire transversale (§5.7.7) qui sont extraites de l'expérience, les skills sont des connaissances procédurales pré-encodées.

**Chargement obligatoire** : avant toute création de fichier ou exécution de code, le système scanne les skills disponibles et charge chaque `SKILL.md` plausiblement pertinent. Cette vérification est inconditionnelle — les skills définissent eux-mêmes leur périmètre.

**Types de skills** : publics (formats de document, design frontend, analyse de données), utilisateur (uploadés), exemples (modèles de référence).

**Routage :**

| Tâche | Skill(s) |
|-------|----------|
| Présentation | `pptx` |
| Tableur | `xlsx` |
| Document Word | `docx` |
| PDF | `pdf` |
| Composant frontend | `frontend-design` |
| Analyse de données CSV | `data-analysis` |
| Fichier uploadé | `file-reading` |

---

### 5.14 Configuration intégrale et versionnée

- Toute la configuration est textuelle (YAML, JSON, Markdown).
- Exemples de fichiers : `workspace/config.yaml` (modèles, canaux, sécurité), `project/config.yaml` (workflow, phases, budgets, outils activés), `project/plan.yaml` (plan détaillé).
- **Versionnement** : tous les fichiers sont stockés dans un système de contrôle de version (Git) pour traçabilité et reproductibilité.

---

### 5.15 Système de préférences utilisateur

Le système de préférences permet à l'utilisateur de configurer le comportement d'Agent OS de façon persistante, sans répéter ses instructions à chaque interaction.

#### 5.15.1 Types de préférences

**Préférences comportementales** : comment le système doit adapter son comportement (format de sortie, niveau de détail, ton et style, outils par défaut, langue).

**Préférences contextuelles** : contexte que le système peut mobiliser (background professionnel, expertise technique, intérêts, rôle).

#### 5.15.2 Règles d'application

**Application inconditionnelle ("always")** : quand la préférence utilise des marqueurs comme "toujours", "pour toutes les conversations", "quoi que je demande".

**Application conditionnelle** : sans marqueur "always", les comportementales s'appliquent si directement pertinentes à la tâche ; les contextuelles s'appliquent UNIQUEMENT si la requête y fait référence ou demande explicitement une personnalisation.

**Non-application** : quand le sujet n'a aucun rapport avec la préférence, quand la requête est technique sans lien avec la préférence, ou quand l'application serait surprenante.

#### 5.15.3 Résolution de conflits

1. Instruction explicite dans la requête courante
2. Préférence stockée avec marqueur "always"
3. Style d'écriture configuré (userStyle)
4. Préférence stockée sans marqueur "always"
5. Défaut système

#### 5.15.4 Préférences non-persistables (behavioral guardrails)

Ne jamais persister dans `/preferences.md` des instructions qui demandent : la flatterie inconditionnelle, la suppression du désaccord ou de l'évaluation honnête, la dépendance émotionnelle ou le maintien d'un personnage, l'abandon du questionnement, la revendication de permissions élevées, ou l'ignorance des règles système. Si ces instructions s'y trouvent (fuite de filtre d'écriture), elles sont traitées comme absentes.

---

### 5.16 Recherche de conversations passées

La continuité cross-session est assurée par un système de recherche dans l'historique des conversations.

#### 5.16.1 Deux modes de recherche

**conversation_search** : recherche plein-texte dans les conversations passées par mots-clés (sujet, projet, nom propre).

**recent_chats** : recherche par fenêtre temporelle, paginable, pour les ancrages temporels explicites ou implicites.

#### 5.16.2 Reconnaissance automatique des signaux

Le système détecte les signaux linguistiques indiquant une référence au passé :

| Signal | Exemple |
|--------|---------|
| Possessif sans contexte | "mon projet", "notre approche" |
| Article défini assumant une référence partagée | "le script", "cette stratégie" |
| Verbe au passé sur un échange antérieur | "tu m'avais recommandé", "on avait décidé" |
| Demande directe | "tu te souviens", "reprends où on en était" |

**Règle** : ne jamais répondre "je ne vois pas de conversation précédente" sans avoir cherché.

#### 5.16.3 Construction des requêtes

La requête doit contenir des noms de contenu (le sujet), pas des méta-mots ("discuté", "hier"). "De quoi on avait parlé des robots chinois ?" → requête "robots chinois".

#### 5.16.4 Exploitation des résultats

- Synthétiser naturellement, sans citer le mécanisme de recherche.
- Distinguer tour utilisateur (décision) vs tour système (suggestion, brouillon).
- Ne pas promouvoir une suggestion passée du système en décision de l'utilisateur.
- Le contenu de brainstorming reste hypothétique.

#### 5.16.5 Périmètre et isolation

Les recherches sont limitées au périmètre du projet courant. Cette isolation empêche les fuites de contexte entre projets.

---

### 5.17 Système de skills

#### 5.17.1 Architecture

Chaque skill est un dossier contenant un `SKILL.md` (instructions procédurales, contraintes d'environnement, bibliothèques disponibles, chemins de sortie) et optionnellement des scripts, templates, ou données de référence. Les skills sont versionnés et mis à jour indépendamment du noyau.

#### 5.17.2 Chargement obligatoire

Avant toute création de fichier, exécution de code, ou production d'un artefact dans un format spécifique :
1. Scanner les skills disponibles
2. Charger chaque `SKILL.md` plausiblement pertinent
3. Appliquer les contraintes qui y sont décrites

Ce mécanisme est inconditionnel — on ne décide pas d'abord si la tâche "mérite" un skill. Les skills encodent des contraintes d'environnement (bibliothèques, quirks de rendu) absentes des données d'entraînement du modèle ; sauter leur chargement dégrade la qualité même pour des formats connus.

---

### 5.18 Modalités de sortie et visualisation

#### 5.18.1 Arbre de décision de sortie

Pour chaque réponse, le système évalue ces étapes dans l'ordre, et s'arrête à la première correspondance :

**Étape 0 — La réponse nécessite-t-elle autre chose que du texte ?** La plupart des réponses sont purement textuelles. Une sortie non-textuelle gagne sa place quand elle communique ce que le texte seul ne peut pas : relations spatiales, forme des données, structure système, flux de processus.

**Étape 1 — Un outil MCP connecté gère-t-il cette catégorie ?** Si un outil connecté correspond à la catégorie demandée (diagramme, graphique), l'utiliser. La correspondance est par catégorie, pas par préférence de style.

**Étape 2 — L'utilisateur demande-t-il un fichier ?** Signaux : "crée un fichier", "sauvegarde", "télécharge", "exporte", extension explicite. Si oui → outils de création de fichiers.

**Étape 3 — Visualiseur inline (défaut)** : widget SVG ou HTML dans le flux de conversation.

#### 5.18.2 Déclencheurs de visualisation

- **Explicites** : "montre-moi", "visualise", "diagramme", "graphique", "illustre".
- **Proactifs** : concept à structure spatiale/séquentielle/systémique, comparaison où un graphique est plus clair, architecture système.
- **Par spécification** : le nom décrit un artefact visuel ("tableau comparatif REST vs GraphQL", "formulaire d'inscription avec email et toggle").

#### 5.18.3 Modules de design

| Module | Usage |
|--------|-------|
| `diagram` | Diagrammes de flux, architecture, séquences |
| `mockup` | Maquettes d'interface, wireframes |
| `interactive` | Widgets interactifs, calculateurs, jeux |
| `chart` | Graphiques de données |
| `art` | Illustrations et contenu visuel créatif |
| `data_viz` | Visualisations de données complexes |

Chaque module définit ses contraintes de rendu (couleurs CSS, dimensions, polices). Le module pertinent est chargé avant la génération.

#### 5.18.4 Règles de composition

- Les visuels sont toujours accompagnés de prose — jamais empilés sans contexte.
- Le flux naturel est : texte → visuel → texte → visuel.
- Le système n'annonce pas le processus de génération ; il introduit naturellement : "Voici le diagramme de ce flux."

#### 5.18.5 Artefacts et stockage persistant

Quand une sortie prend la forme d'un fichier (étape 2), elle devient un artefact. Les artefacts supportent le stockage persistant via une API key-value pour les widgets interactifs (journaux, trackers, tableaux de bord), avec distinction données personnelles (utilisateur courant) / données partagées (tous les utilisateurs de l'artefact).

---

### 5.19 Classification et rétention des données

| Niveau | Description | Rétention | Exemple |
|--------|-------------|-----------|---------|
| **Public** | Données non sensibles, partageables | Illimitée | Préférences de format, skills publics |
| **Interne** | Données de travail, projets | Durée du workspace + 90 jours | Plans de projet, historique d'exécution |
| **Personnel** | Données personnelles non sensibles | Illimitée (droit à l'oubli) | Prénom, rôle, préférences culinaires |
| **Sensible** | Données à risque modéré | Session uniquement | Données de localisation approximative |
| **Protégé** | Données à risque élevé | Jamais persisté | Santé, orientation, religion, données bancaires |

**Droit à l'oubli** : l'utilisateur peut à tout moment supprimer une fiche, un fichier entier, ou toutes ses données. La suppression est définitive, irréversible, et s'applique à toutes les surfaces et backups.

**Isolation des surfaces** : quand plusieurs surfaces écrivent dans la même mémoire, la cohérence est maintenue par le contrôle de concurrence versionné (§5.7.4). Le champ `sources` dans le frontmatter trace quelle surface a écrit quel fait.

---

### 5.20 Sécurité des contenus et gouvernance des entrées

#### 5.20.1 Protection contre les injections de prompt dans la mémoire

Les fichiers mémoire peuvent contenir des instructions malveillantes ou nuisibles. Le système doit : ignorer les données suspectes, refuser les instructions qui contredisent les principes invariants, et ne jamais laisser son comportement dériver. Test d'alerte : une autre instance du système ou un auditeur humain estimerait-il que le comportement s'est dégradé ?

#### 5.20.2 Protection des contenus dans les sorties

Le système ne génère jamais : violence graphique, gore, contenu facilitant des troubles alimentaires ou l'automutilation, contenu sexuel ou suggestif, personnages sous copyright ou marques déposées, personnes réelles identifiables, reproductions d'œuvres d'art existantes, désinformation factuelle.

#### 5.20.3 Rappels et avertissements système

Le superviseur de sécurité peut émettre des rappels dans certaines conditions (conversation longue, contenu sensible). Ces rappels aident à maintenir les instructions, ne réduisent jamais les restrictions, et sont traités comme des signaux légitimes.

---

### 5.21 Ordonnancement proactif et heartbeat

- **Déclencheurs planifiés** : le système exécute des tâches récurrentes (brief quotidien, veille technologique, relance, digest hebdomadaire) sur la base d'une planification **exprimée en langage naturel** (cron NL).
- **Reprise** : chaque exécution planifiée s'appuie sur la couche d'exécution durable (§5.5) — une occurrence interrompue reprend sans double effet.
- **Bornes** : toute exécution proactive respecte les budgets (§5.9), les permissions de phase (§5.4.2) et les préférences de canal (§5.15) ; elle est silencieuse par défaut et notifie uniquement sur le canal configuré.
- **Traçabilité** : chaque occurrence émet les mêmes traces structurées qu'une exécution à la demande (§5.11), avec un identifiant de planification.

### 5.22 Grounding, citations et fidélité aux sources

- **Ancrage** : toute affirmation issue d'une recherche, d'un document ou d'une mémoire porte une **citation** vers sa source (URL, fichier, entrée mémoire avec sa provenance).
- **Distinction fait / inférence** : une inférence ne peut jamais être présentée comme un fait ; elle est étiquetée comme telle (cohérent avec la provenance `[inferred]`, §5.7.2).
- **Score de fidélité** : la fidélité aux sources est mesurée par l'évaluation continue (§5.10/§5.11) et exposée dans les tableaux de bord.
- **Effondrement de contexte** : les citations renvoient à la source, jamais à un résumé auto-réécrit, ce qui évite l'érosion du détail (§5.2.4).

---

## 6. Exigences non-fonctionnelles

| ID | Catégorie | Exigence |
|----|-----------|----------|
| NF-01 | Performance | Le temps de réponse perçu pour une interaction simple doit être inférieur à 2 secondes. |
| NF-02 | Scalabilité | Le système doit supporter plusieurs projets simultanés (au moins 10) sur un même workspace. |
| NF-03 | Sécurité | Toute exécution de code est isolée dans un conteneur aux privilèges réduits. |
| NF-04 | Fiabilité | Toute action de longue durée s'exécute via la couche d'exécution durable (§5.5) avec retry et reprise après panne. |
| NF-05 | Maintenabilité | L'architecture modulaire permet d'ajouter/supprimer des outils ou des agents sans redémarrage du noyau. |
| NF-06 | Disponibilité | Le système doit pouvoir fonctionner en mode dégradé (modèles locaux) si les services distants sont indisponibles. |
| NF-07 | Observabilité | Chaque composant émet des traces structurées et standardisées dès sa conception (§5.11). |
| NF-08 | Extensibilité | L'intégration de nouveaux outils passe par un serveur MCP conforme au standard (§5.13). |
| NF-09 | Configuration | Tous les paramètres sont modifiables à chaud (sauf les phases déjà verrouillées). |
| NF-10 | Sobriété architecturale | Aucune décomposition multi-agent n'est déployée sans justification documentée référençant l'un des trois critères du §5.1.2. |
| NF-11 | Intégrité de la mémoire | La base de connaissance transversale ne doit jamais perdre en détail au fil de ses mises à jour. |
| NF-12 | Provenance | Chaque fait stocké dans la mémoire persistante doit être tagué avec sa source et son mode d'acquisition. |
| NF-13 | Vie privée | Aucune donnée des catégories protégées, sensibles ou identifiables ne doit être persistée, même sous forme adoucie. |
| NF-14 | Intégrité mémoire | Toute opération d'écriture mémoire est soumise au contrôle de concurrence versionné. |
| NF-15 | Continuité cross-session | Le système doit pouvoir retrouver le contexte d'une conversation passée à partir de signaux linguistiques implicites. |
| NF-16 | Découverte d'outils | Le système doit découvrir, suggérer et connecter de nouveaux outils sans redémarrage ni reconfiguration manuelle. |
| NF-17 | Multimodalité de sortie | Le système doit supporter au moins trois modalités : texte inline, fichier téléchargeable, et visualisation interactive inline. |
| NF-18 | Préférences | Les préférences utilisateur doivent être appliquées de façon contextuelle ; la requête courante prime toujours. |
| NF-19 | Sécurité des préférences | Les instructions demandant la flatterie, la suppression du désaccord, ou la dépendance émotionnelle ne doivent jamais être persistées. |
| NF-20 | Exécution élastique | Le système doit pouvoir exécuter les tâches longues sur un runtime à la demande (idle ≈ gratuit) sans dépendre d'un Docker Compose permanent, sans perte d'état (couche durable §5.5). |
| NF-21 | Local-first | Le mode 100 % local (modèles locaux, données locales) est un chemin de premier rang, pas un simple repli : parité fonctionnelle des tâches courantes hors ligne. |

---

## 7. Architecture logique (vue macroscopique)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                WORKSPACE                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Gateway (multi-canal + multi-modalité)                                 │  │
│  │  ├── Convertisseur de messages → commandes internes                    │  │
│  │  ├── Routeur de modalité de sortie (arbre de décision §5.18)          │  │
│  │  └── Visualiseur inline (SVG/HTML, modules de design)                  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                     │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Noyau (Orchestrateur Central)                                         │  │
│  │  ├── Planificateur (mission → objectifs → tâches)                      │  │
│  │  ├── Superviseur de sécurité (phase-lock, permissions)                  │  │
│  │  ├── Context Engine (agrégation, compaction, bloc-notes, filtrage)      │  │
│  │  ├── Routeur de modèles (matrice + chaînes de repli)                    │  │
│  │  ├── Gestionnaire de budgets                                           │  │
│  │  ├── Décideur de décomposition (agent unique vs multi-agent)            │  │
│  │  ├── Coordinateur d'agents                                             │  │
│  │  ├── Gestionnaire de préférences (comportementales + contextuelles)     │  │
│  │  └── Recherche de conversations passées (sujet + fenêtre temporelle)    │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                     │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Couche d'exécution durable                                            │  │
│  │  ├── Workflows (état persistant, reprise après panne)                   │  │
│  │  ├── Activités (retry policies, idempotence)                           │  │
│  │  ├── Compensation (pattern saga)                                       │  │
│  │  └── Signaux d'approbation humaine longue durée                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                     │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Agents et sous-agents                                                 │  │
│  │  ├── Chef d'orchestre (Conductor)                                       │  │
│  │  ├── Agents spécialisés (par contexte, pas par métier)                  │  │
│  │  ├── Sous-agents dynamiques                                            │  │
│  │  └── Sous-agents de vérification                                       │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                     │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Outils et écosystème de découverte                                    │  │
│  │  ├── Serveurs MCP (protocole d'extension standard)                      │  │
│  │  ├── Découverte dynamique (tool_search, chargement différé)            │  │
│  │  ├── Registre MCP (search_mcp_registry)                                 │  │
│  │  ├── Suggestion de connecteurs (suggest_connectors)                     │  │
│  │  ├── Skills (modules de compétence pré-encodés)                         │  │
│  │  ├── Outils internes (système de fichiers, réseau, shell)               │  │
│  │  └── Outils externes (API, bases de données, services)                  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                     │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Persistance et mémoire                                                │  │
│  │  ├── Système de fichiers mémoire (taxonomie, provenance, versions)      │  │
│  │  ├── Base de connaissances transversale (skills, deltas incrémentaux)   │  │
│  │  ├── Préférences utilisateur (comportementales + contextuelles)         │  │
│  │  ├── Historique des conversations (recherche par sujet et date)         │  │
│  │  ├── Projets (worktrees) avec fichiers, historique, config              │  │
│  │  ├── Artefacts (fichiers + stockage key-value pour widgets)             │  │
│  │  └── Journaux (traces)                                                  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                     │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Observabilité & Gouvernance (transversal à toutes les couches)         │  │
│  │  ├── Traces standardisées (spans agent / outil / modèle)                │  │
│  │  ├── Évaluation continue (dérive, succès, fidélité, sécurité)            │  │
│  │  ├── Classification et rétention des données (5 niveaux)                │  │
│  │  └── Tableaux de bord (coût, fiabilité, auditabilité)                    │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Méthode de construction (feuille de route)

Ordre recommandé, chaque étape étant solidifiée avant la suivante :

1. **Boucle de base** (proposition → validation → exécution → observation), instrumentée dès le départ.
2. **Outils** (capacités d'action, accès fichiers, réseau) via serveurs MCP.
3. **Permissions** (qui a le droit de faire quoi).
4. **Observations et évaluation continue** (capture, analyse, scores de succès).
5. **Budgets** (limitations et seuils).
6. **Traçage standardisé** (spans agent/outil/modèle, portables).
7. **Exécution durable** (workflows, retry, reprise après panne).
8. **Planification** (décomposition mission/objectifs/tâches).
9. **Gestion active du contexte** (compaction automatique, bloc-notes externalisé).
10. **Système de fichiers mémoire avec provenance** — taxonomie, tagging, contrôle de concurrence versionné, règles d'omission.
11. **Mémoire incrémentale** (cycle génération/réflexion/curation, deltas).
12. **Préférences utilisateur** — stockage, application contextuelle, résolution de conflits, guardrails.
13. **Compétences et connecteurs** (spécialisation, intégration services tiers).
14. **Écosystème de découverte d'outils** — tool_search, search_mcp_registry, suggest_connectors, skills.
15. **Recherche de conversations passées** — conversation_search, recent_chats, signaux linguistiques.
16. **Modalités de sortie et visualisation** — arbre de décision, visualiseur inline, modules de design.
17. **Décision et boucle multi-agent** (activée seulement quand un des trois critères du §5.1.2 est mesuré en production).
18. **Sous-agents et vérification** (agents spécialisés indépendants, pattern de vérification).
19. **Classification et rétention des données** (5 niveaux, droit à l'oubli).
20. **Workspaces et worktrees** (isolation et branches).

---

## 9. Glossaire

- **Agent** : composant logiciel autonome, ayant un rôle, des outils et un modèle d'IA associé.
- **Sous-agent** : agent instancié pour une tâche spécifique, héritant d'un sous-ensemble filtré du contexte de son parent.
- **Sous-agent de vérification** : agent dont le seul rôle est de valider le travail d'un autre agent en boîte noire.
- **Contexte** : ensemble des informations pertinentes pour une étape donnée — traité comme une ressource finie.
- **Dégradation du contexte (context rot)** : perte de qualité de raisonnement à mesure que le contexte grandit.
- **Compaction** : résumé automatique de l'historique pour libérer de l'espace de contexte.
- **Effondrement du contexte (context collapse)** : dégradation progressive d'une base de connaissance par réécritures complètes répétées.
- **Biais de brièveté** : tendance à privilégier un résumé court au détriment d'un détail utile.
- **Décomposition par contexte** : règle de découpage multi-agent fondée sur l'isolation du contexte.
- **Jeu du téléphone** : dégradation de l'information à chaque transfert de contexte dans un découpage par métier.
- **Exécution durable** : garantie qu'une action longue survit à une panne et reprend exactement où elle s'est arrêtée.
- **Activité (durable)** : unité d'action encapsulée avec sa propre politique de retry.
- **Compensation (saga)** : action inverse pour annuler les effets d'une séquence partiellement exécutée.
- **MCP (Model Context Protocol)** : standard ouvert d'intégration entre un agent et des outils/services externes.
- **Trace / span** : unité structurée et standardisée d'observabilité.
- **Phase** : étape du cycle de vie d'un projet (CLASSIFY, KNOW, PLAN, DEBATE, APPROVE, BUILD, QUALITY, AUTOEVAL, MEMORY, OBSERVE).
- **Phase-lock** : restriction des permissions en fonction de la phase en cours.
- **Worktree** : branche de travail d'un projet, permettant des explorations parallèles.
- **Workspace** : conteneur racine regroupant plusieurs projets, mémoire transversale et configuration globale.
- **Skill** : fiche de compétence extraite de l'expérience, mise à jour de façon incrémentale.
- **Provenance** : métadonnée indiquant comment un fait a été acquis (`[stated]`, `[observed]`, `[inferred]`).
- **Jeton de version (if_version)** : identifiant de concurrence requis pour toute écriture mémoire.
- **Préférence comportementale** : instruction sur le comportement du système (format, ton, outils, langue).
- **Préférence contextuelle** : information sur l'utilisateur mobilisable dans les contextes pertinents.
- **Behavioral guardrail** : règle empêchant la persistance de préférences dangereuses.
- **Registre MCP** : annuaire externe de connecteurs disponibles.
- **Arbre de décision de sortie** : processus en 3 étapes déterminant la modalité de réponse.
- **Visualiseur inline** : moteur de rendu SVG/HTML pour widgets interactifs dans le flux.
- **Artefact** : fichier créé par le système avec support de stockage persistant.
- **conversation_search** : recherche plein-texte dans l'historique par mots-clés.
- **recent_chats** : recherche dans l'historique par fenêtre temporelle.
- **Signal linguistique** : marqueur indiquant une référence à une conversation passée.
- **Classification de rétention** : niveau déterminant la durée de conservation d'une donnée.
- **Skill (module)** : dossier de meilleures pratiques pré-encodées, chargé obligatoirement avant création.

---

## 10. Annexes

### A. Format d'une fiche de compétence (skill), avec compteur incrémental

```yaml
id: skill-123
nom: "Revue de code efficace"
description: "Méthode pour détecter les erreurs courantes en Python"
domaine: ["développement", "qualité"]
prerequis: ["outil de linting", "base de données d'erreurs"]
conditions_succes: ["réduction de 30% des erreurs", "temps moyen de revue < 10 min"]
compteur:
  aidant: 14
  nuisant: 1
  derniere_maj: "2026-07-18"
exemples:
  - contexte: "projet X"
    resultat: "15 bugs détectés en 5 min"
```

### B. Exemple de workflow déclaratif (extrait)

```yaml
phases:
  - id: PLAN
    allowed_tools: [planner, memory_reader]
    required_approval: human
    next: [BUILD, ABORT]
  - id: BUILD
    allowed_tools: [code_generator, file_writer]
    execution: durable
    retry_policy:
      max_attempts: 3
      backoff: exponential
    next: [QUALITY]
  - id: QUALITY
    allowed_tools: [test_runner, verifier_subagent]
    verification:
      require_full_suite: true
      require_negative_tests: true
    next: [AUTOEVAL]
```

### C. Décision de décomposition multi-agent (checklist)

Avant d'activer une architecture multi-agent, le système doit pouvoir répondre "oui" à au moins une question, avec preuve chiffrée :

1. Une sous-tâche produit-elle régulièrement plus de ~1000 tokens de contenu non pertinent pour la suite ? *(protection de contexte)*
2. La tâche se décompose-t-elle en sous-problèmes véritablement indépendants, sans dépendance ni état partagé ? *(parallélisation)*
3. L'agent gère-t-il plus de ~15-20 outils, ou des domaines d'outils non liés, ou des consignes comportementales contradictoires ? *(spécialisation)*

Si la réponse est non aux trois, rester en agent unique.

### D. Squelette de trace structurée (span d'invocation d'agent)

```yaml
span_type: invoke_agent
agent: "conductor"
attributes:
  gen_ai.request.model: "modele-configure"
  gen_ai.usage.input_tokens: 1840
  gen_ai.usage.output_tokens: 320
  duration_ms: 1240
children:
  - span_type: execute_tool
    tool: "mcp.filesystem.read"
  - span_type: chat
    gen_ai.response.finish_reason: "tool_use"
```

### E. Exemple de sous-agent de vérification (consigne type)

```text
Rôle : vérifier l'implémentation, pas la comprendre.
Critères : {liste explicite des critères de réussite}
Consigne obligatoire :
  - Exécuter la suite de tests complète, pas un sous-ensemble.
  - Tenter au moins un cas qui doit échouer et confirmer qu'il échoue.
  - Ne marquer "PASSED" que si tous les tests passent sans exception.
  - Rapporter chaque échec individuellement, sans résumer en "globalement OK".
```

### F. Format d'un fichier mémoire avec frontmatter complet

```yaml
---
name: auth-redesign
description: Refonte du système d'authentification — contraintes, décisions, statut
sources: [chat, claude-code]
aliases: [auth-migration, login-v2]
---

- [stated] le nouveau système doit supporter OAuth2 et SAML
- [stated] la migration doit être transparente pour les utilisateurs existants
- [stated] deadline : Q4 2026
- [observed] 3 PRs ouvertes, 2 reviewées, 0 mergées
- [inferred] complexité estimée élevée (confiance: 0.8) basé sur le nombre d'intégrations
```

### G. Matrice d'application des préférences

```yaml
preferences:
  behavioral:
    - type: format
      rule: "utilise des listes à puces pour les réponses techniques"
      scope: selective
    - type: langue
      rule: "réponds toujours en français"
      scope: always
  contextual:
    - type: expertise
      rule: "développeur Python senior"
      scope: selective
    - type: background
      rule: "travaille dans la finance"
      scope: selective
```

### H. Squelette d'un skill (SKILL.md)

```markdown
# skill: pdf

## déclencheurs
- création, lecture, modification de fichiers PDF
- extraction de texte/tableaux
- fusion, séparation, rotation de pages

## contraintes d'environnement
- bibliothèque: pypdf
- polices disponibles: (liste)
- taille maximale: 100 Mo

## procédure
1. Vérifier le type de PDF (texte, scanné, formulaire)
2. Choisir la stratégie d'extraction appropriée
3. ...
```

### I. Arbre de décision de sortie (pseudo-code)

```
fonction router_sortie(demande):
    si demande_purement_textuelle(demande):
        retourner reponse_texte()

    outil_mcp = trouver_outil_mcp_pertinent(demande)
    si outil_mcp:
        retourner utiliser_outil_mcp(outil_mcp)

    si demande_fichier_explicite(demande):
        retourner creer_fichier(demande)

    si contenu_merite_visualisation(demande):
        retourner visualiser_inline(demande)

    retourner reponse_texte()
```

---

## 11. Sources et références (juillet 2026)

- Anthropic Engineering — *Effective context engineering for AI agents* (contexte comme ressource finie, dégradation du contexte, curation des outils, few-shot canonique).
- Anthropic Engineering — *Writing effective tools for AI agents* (découverte dynamique d'outils, réponses économes en contexte, évolution du protocole MCP).
- Claude (Anthropic) — *Building multi-agent systems: when and how to use them* (23 janvier 2026) — décision framework, décomposition par contexte, jeu du téléphone, sous-agent de vérification, biais de "victoire prématurée", multiplicateurs de coût 3-10x / 15x.
- Zhang et al. — *Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models* (arXiv:2510.04618) — biais de brièveté, effondrement du contexte, mises à jour incrémentales par delta, rôles génération/réflexion/curation, mécanisme de croissance-et-raffinage.
- Documentation et guides de production Temporal / Claude Agent SDK (2026) — séparation raisonnement/exécution durable, politiques de retry, pattern de compensation (saga), reprise après panne, points d'approbation humaine longue durée.
- OpenTelemetry — conventions sémantiques GenAI (`gen_ai.*`), conventions de spans d'agents (`invoke_agent`, `execute_tool`, `chat`) — standardisation de l'observabilité des agents.
- Anthropic Engineering — *How we built our multi-agent research system* — pattern orchestrateur-ouvriers, mémoire persistée du plan avant saturation du contexte.
- **Claude Fable 5 — System Prompt & Behavior Configuration (Anthropic, juillet 2026)** — système de fichiers mémoire avec provenance, taxonomie structurée, tagging `[stated]`/`[observed]`/`[inferred]`, contrôle de concurrence versionné, règles d'omission par catégorie, behavioral guardrails, règles d'application de la mémoire (never/always/selectively), principe "earn its place", garde-fous anti-sur-familiarité.
- **Claude Fable 5 — Tool Ecosystem** — chargement différé (`tool_search`), registre MCP (`search_mcp_registry`), suggestion de connecteurs (`suggest_connectors`), distinction first-party/third-party, priorité des outils.
- **Claude Fable 5 — Past Conversation Retrieval** — `conversation_search`, `recent_chats`, signaux linguistiques, règles d'exploitation des résultats.
- **Claude Fable 5 — Output Routing & Visualization** — arbre de décision 3 étapes, visualiseur inline SVG/HTML, modules de design, artefacts avec stockage persistant.
- **Claude Fable 5 — Skills System** — dossiers de meilleures pratiques, chargement obligatoire, contraintes d'environnement encodées.
- **Claude Fable 5 — Preferences System** — préférences comportementales vs contextuelles, règles d'application, résolution de conflits, catégories non-persistables.

*Ces sources reflètent l'état des pratiques publiées à la date de rédaction (juillet 2026) et sont susceptibles d'évoluer.*

---

**Fin du document SFD v3.1.**
