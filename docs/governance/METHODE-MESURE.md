# Règles de méthode — mesure, vérification et gardes

> Créé au Sprint 5 (v11 §3). Ces règles **doivent survivre au rapport** qui les
> a produites : un rapport est un instantané, une règle est un outil.

Une règle qui vit dans un rapport est perdue au rapport suivant. Celles-ci sont
nées de trois mistakenly-closed portes et d'un faux positif que j'ai produit
moi-même ; elles sont donc datées, motivées, et **bornées** — chacune dit le
cas d'où elle vient, pour qu'on sache où elle cesse de s'appliquer.

---

## R1 — Un décompte de sous-chaîne n'est pas une mesure

*Origine* : v10 §2. Deux fois en deux jours j'ai announced un nombre lu par
`grep` : « 421 arêtes » (v1), « le bus de pensées, 11 fichiers » (v9), « 0
paquet branché sur 10 » (v10, paquet 1). Le troisième est instructif : les
paquets sont **TypeScript**, la mesure cherchait dans les fichiers
**Python**. Elle ne pouvait pas les voir — et le paquet était branché.

**Règle.** Toute grandeur de comptage — fichiers, arêtes, appelants, occurrences,
références — se mesure par **résolution structurelle** : existence de fichier,
résolution d'import, résolution de symbole, **parsing** du format (un `.json`
parsé, pas lu), et pour le code un **AST**.

**Borne.** Cette règle ne dit pas que le texte est inutile : elle dit qu'un
texte ne suffit pas. Une recherche de sous-chaîne reste légitime pour **trouver
un candidat**, jamais pour **établir un fait**. Écrire la distinction dans le
rapport de mesure : « trouvé 14 candidats, vérifié 9 », et non « 9 sur 14 ».

---

## R2 — Vérifier l'affirmation, pas seulement le chemin

*Origine* : v11 §1. `src/durable_execution.py` existe. La compensation de saga
n'y est pas exécutée. J'avais conclu « ABSENTE » — à tort — parce que
`_handle_step_failure` porte le nom de son **déclencheur**, et que ma recherche
cherchait un nom portant `compens`. Le port TypeScript, lui, a bien
`async compensate(id)` : l'affirmation d'origine ne parlait pas du bon port.

**Règle.** Quand une affirmation porte sur une **capacité**, la lecture
s'arrête au **ce que le code définit** : la branche existe-t-elle, est-elle
atteignable, **exécute-t-elle quelque chose** ? Trois questions distinctes, et
« le fichier existe » n'est aucune des trois.

**Contre-exemple qui fait la règle** : un chemin existe, une branche existe, un
statut est écrit — et rien n'est exécuté. C'est l'état réel de la compensation,
et il n'a ni nom dans « présent » ni dans « absent ».

**Borne.** La règle coûte cher : elle impose de lire, pas de comparer. Elle
s'applique aux affirmations de capacité, pas aux affirmations de présence —
`src/x.py` existe-t-il ? se répond par existence.

---

## R3 — Un décompte par substring ne devient pas une porte

*Origine* : v10, même affaire que R1, mais du côté de la **garantie**. Une
mesure par sous-chaîne produit un seuil juste faux (10 au lieu de 9) qui a
duré un sprint, parce que la porte qu'elle alimentait était verte.

**Règle.** Une grandeur destinée à être gelée est d'abord vérifiée par
**deux mesures indépendantes** — deux implémentations, pas la même exécutée
deux fois. L'accord n'est pas une coïncidence à constater, c'est la preuve que
la mesure mesure ce qu'elle dit mesurer.

---

## R4 — Un garde a au moins un test sur entrée cassée

*Origine* : v9 §2, puis v11 §3.2. Le `sys.exit(1)` de `verifier()` a été
remplacé par `pass`, et **neuf tests sont restés verts** : tous testaient
l'outil dans son état sain, où la sortie est 0 et où le garde n'a rien à faire.

**Règle.** Tout garde ou vérificateur doit avoir un test qui **exécute l'outil
sur une entrée volontairement cassée** et affirme **qu'il échoue**. Un garde
dont on ne teste que le chemin heureux n'est pas à moitié testé : il est **non
testé**, et il donne une assurance imaginaire.

**Borne.** Un test d'entrée cassée se prouve lui-même par la mutation qu'il
est censé attraper. Sans cette mutation, on ne sait pas si le test casse
quelque chose ou s'il échoue pour une autre raison — ce qui est arrivé, et
qui se voit dans le lot de mutations suivant.

---

## R5 — Une règle dérivée d'un seul cas porte son périmètre

*Origine* : v11 §3.3. « Une porte à 0 est une porte cassée » (Sprint 4) est
vrai d'une grandeur qui doit **descendre** : à 0, plus rien ne peut la
dépasser. La règle a été dérivée de ce cas, puis écrite comme absolue — et une
grandeur de **conformité** legitimately à 0.

**Règle.** Toute règle nouvelle énonce le **cas dont elle est tirée**, et ce
qui la fait cesser de s'appliquer. Une règle qui ne sait pas où elle s'arrête
n'est pas une règle, c'est un dogme : on l'applique alors qu'elle a tort, et on
la contourne quand elle a raison.

**Application immediately posée.** Seuil `sens: conformance` : sa non-vacuité
est **prouvée** sur un dépôt fabriqué, sinon l'élargissement serait un
assouplissement.

---

## R6 — Une mutation qui ne s'applique pas est morte, jamais une réussite

*Origine* : v11 §3.3, en continuation. Un harnais qui n'applique pas sa
mutation affiche « MUTATION NON APPLIQUÉE » sur `stderr`, et la mutation est
**enregistrée comme morte** — jamais comptée comme capturée. Une mutation
inerte qui ne change rien ne prouve rien, et la compter gonflerait le taux
de mutation d'un test qui, lui, n'a peut-être jamais rien gardé.

Deux mutations de ce chantier ont été inertes : changer l'extension d'un
fichier non parsé, et une ancre qui ne fut pas unique. Les deux sont notées
comme telles, et remplacées par la mutation qui visait réellement le défaut.

---

## R7 — Un chemin périmé reconnu n'est pas une capacité fantôme

*Origine* : v10 §1. Deux listes, jamais une : `CHEMINS_PERIMES` (périmé, avec
où la capacité se trouve) et `CHEMINS_RETIRES` (n'a jamais existé). Et la
distinction `code` / `note` : un chemin retiré cité dans une `note` est un
**constat**, accepté ; réaffirmé dans `code`, c'est une **prétention**, et ça
fait échouer l'outil.

**Règle.** « Absent », « périmé » et « jamais existé » sont trois états. Les
confondre coûte deux fois : on efface une information, ou on fabrique un
fantôme à déplorer.

---

## Ce que ces règles ne couvrent pas

Elles portent sur la **mesure** et sur les **gardes**. Elles ne disent rien
d'un arbitrage de politique : ce que vaut une capacité, et si un doublon doit
être archivé ou branché, reste une décision, pas une mesure. Le dossier
`MOD-9-DOSSIER.md` le pose sans le trancher, et c'est délibéré.
