# RFC-NNNN : Titre de la proposition

**Statut :** [Brouillon | En revue | Accepté | Rejeté | Implémenté]

**Auteur(s) :** [Nom ou @github]

**Date de création :** [AAAA-MM-JJ]

**Date de dernière modification :** [AAAA-MM-JJ]

**Durée de la période de commentaires :** [AAAA-MM-JJ] au [AAAA-MM-JJ] (minimum 7 jours)

---

## 1. Résumé exécutif

*Un paragraphe (3-5 phrases) qui résume le changement proposé, pourquoi il est nécessaire, et l'impact attendu. Doit être compréhensible par un lecteur non technique.*

---

## 2. Contexte et motivation

### 2.1 Problème actuel

*Décrire le problème que cette RFC cherche à résoudre. Inclure des données chiffrées si disponibles (ex. performance, coût, temps de développement).*

### 2.2 Pourquoi maintenant ?

*Expliquer pourquoi ce changement est prioritaire maintenant plutôt que plus tard. Qu'est-ce qui a changé dans l'environnement, les besoins utilisateurs, ou la technologie ?*

### 2.3 Qui est impacté ?

| Partie prenante | Impact | Niveau |
|-----------------|--------|:------:|
| Utilisateurs finaux | *Description* | Faible / Moyen / Élevé |
| Administrateurs système | *Description* | Faible / Moyen / Élevé |
| Développeurs contributeurs | *Description* | Faible / Moyen / Élevé |
| Services dépendants | *Description* | Faible / Moyen / Élevé |

### 2.4 Références

- Liens vers des issues GitHub, discussions, ADR, ou documentation pertinente
- Liens vers des RFCs similaires dans d'autres projets
- Standards ou spécifications techniques de référence

---

## 3. Proposition

### 3.1 Vue d'ensemble

*Schéma ou description textuelle de l'architecture cible. Un diagramme est fortement recommandé (ASCII art ou lien vers un schéma Kroki).*

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Composant  │────▶│  Composant  │────▶│  Composant  │
│  Actuel     │     │  Modifié    │     │  Nouveau    │
└─────────────┘     └─────────────┘     └─────────────┘
```

### 3.2 Changements détaillés

#### 3.2.1 Modification 1 : [Titre]

- **Fichier(s) impacté(s) :** `chemin/fichier.py`
- **Type de changement :** Ajout / Modification / Suppression / Refactor
- **Description technique :**
  ```
  Décrire précisément ce qui change, avec des extraits de code si pertinent.
  ```
- **Raison :** Pourquoi cette modification spécifique

#### 3.2.2 Modification 2 : [Titre]

*(Répéter pour chaque changement significatif)*

### 3.3 Migration et rétrocompatibilité

| Scénario | Compatible ? | Action requise |
|----------|:------------:|----------------|
| Mise à jour depuis vX.Y.Z | Oui / Non / Partiel | *Description* |
| Déploiement fresh install | Oui / Non | *Description* |
| Rollback | Oui / Non | *Description* |

### 3.4 Plan de déploiement

1. **Phase 1** : [Description] — [Durée estimée]
2. **Phase 2** : [Description] — [Durée estimée]
3. **Phase 3** : [Description] — [Durée estimée]

### 3.5 Plan de rollback

*Étapes précises pour revenir à l'état antérieur en cas d'échec. Doit pouvoir être exécuté en < 30 minutes.*

---

## 4. Alternatives considérées

### 4.1 Alternative A : [Titre]

| Critère | Évaluation |
|---------|-----------|
| **Description** | *Résumé de l'alternative* |
| **Avantages** | *Pourquoi cette alternative est intéressante* |
| **Inconvénients** | *Pourquoi elle n'a pas été retenue* |
| **Coût estimé** | *Temps de développement, complexité, impact* |
| **Raison du rejet** | *Argument décisif* |

### 4.2 Alternative B : Ne rien faire

| Critère | Évaluation |
|---------|-----------|
| **Description** | Conserver l'état actuel sans changement |
| **Avantages** | Zéro risque, zéro effort |
| **Inconvénients** | *Qu'est-ce qui se dégrade si on ne fait rien ?* |
| **Raison du rejet** | *Pourquoi le statu quo n'est pas acceptable* |

---

## 5. Analyse d'impact

### 5.1 Impact technique

| Dimension | Impact | Détail |
|-----------|:------:|--------|
| Performance | + / - / Neutre | *Description* |
| Sécurité | + / - / Neutre | *Description (surface d'attaque, permissions)* |
| Fiabilité | + / - / Neutre | *Description (SLO, RTO, RPO)* |
| Complexité | + / - / Neutre | *Description (dette technique, maintenance)* |
| Observabilité | + / - / Neutre | *Description (traces, métriques, logs)* |
| Tests | + / - / Neutre | *Description (couverture, nouveaux tests)* |

### 5.2 Impact sur les services Docker

| Service | Impact | Action requise |
|---------|:------:|----------------|
| `odysseus` | Aucun / Mineur / Majeur | *Description* |
| `agentos-engine` | Aucun / Mineur / Majeur | *Description* |
| `agentos-sandbox` | Aucun / Mineur / Majeur | *Description* |
| *[autres services]* | | |

### 5.3 Impact sur les principes invariants

*Vérifier les 22 principes de la SFD v3.1. La proposition en viole-t-elle ou en renforce-t-elle ?*

| Principe | Impact | Justification |
|----------|:------:|---------------|
| P1 — Le risque modifie la boucle | ✅ / ⚠️ / ❌ | |
| P4 — Budgets obligatoires | ✅ / ⚠️ / ❌ | |
| P11 — Commencer simple | ✅ / ⚠️ / ❌ | |
| P14 — Survie aux pannes | ✅ / ⚠️ / ❌ | |
| *[principes pertinents]* | | |

### 5.4 Impact budgétaire

| Poste | Coût estimé |
|-------|:-----------:|
| Développement | *Jours-homme* |
| Tests | *Jours-homme* |
| Documentation | *Jours-homme* |
| Consommation tokens supplémentaire | *Estimation mensuelle* |
| Infrastructure supplémentaire | *RAM, CPU, stockage* |

---

## 6. Calendrier

| Jalon | Date cible | Livrable |
|-------|:----------:|----------|
| Fin de la période de commentaires | [AAAA-MM-JJ] | RFC acceptée ou rejetée |
| Début implémentation | [AAAA-MM-JJ] | Branche de travail |
| PR ouverte | [AAAA-MM-JJ] | Code + tests + docs |
| Merge | [AAAA-MM-JJ] | Déploiement |

---

## 7. Questions ouvertes

*Lister les questions qui doivent être résolues avant que la RFC puisse être acceptée.*

- [ ] Question 1 : *Description* — @responsable
- [ ] Question 2 : *Description* — @responsable

---

## 8. Décision

*À remplir après la période de commentaires.*

- [ ] **Accepté** — L'implémentation peut commencer selon le calendrier ci-dessus.
- [ ] **Accepté avec modifications** — Voir les changements demandés dans les commentaires.
- [ ] **Rejeté** — Voir la raison dans les commentaires.
- [ ] **Reporté** — Reconsidéré le [AAAA-MM-JJ].

**Décideur(s) :** [Nom(s)]

**Date de la décision :** [AAAA-MM-JJ]

---

## Annexe : Checklist de soumission

- [ ] Le résumé exécutif est compréhensible par un non-technicien
- [ ] Au moins 2 alternatives sont documentées et comparées
- [ ] L'impact sur la rétrocompatibilité est explicite
- [ ] Un plan de rollback est défini
- [ ] Les principes SFD pertinents sont vérifiés
- [ ] Les questions ouvertes sont identifiées
- [ ] La RFC est postée dans le canal de discussion approprié
