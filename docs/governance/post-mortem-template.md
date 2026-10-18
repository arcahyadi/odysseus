# Post-Mortem — [Titre de l'incident]

**Statut :** [Brouillon | En revue | Publié]

**Date de l'incident :** [AAAA-MM-JJ]

**Date du rapport :** [AAAA-MM-JJ]

**Auteur(s) :** [Nom(s)]

---

## 1. Synthèse

| Attribut | Valeur |
|----------|--------|
| **Incident ID** | INC-YYYY-NNN |
| **Sévérité** | SEV1 / SEV2 / SEV3 |
| **Date et heure de début** | AAAA-MM-JJ HH:MM UTC |
| **Date et heure de fin** | AAAA-MM-JJ HH:MM UTC |
| **Durée totale** | X heures, Y minutes |
| **Services affectés** | *Liste des services Docker impactés* |
| **Utilisateurs affectés** | *Nombre ou pourcentage estimé* |
| **Détecté par** | *Healthcheck / ntfy / utilisateur / workflow automatisé* |

### Résumé en une phrase

*Décrire l'incident en une phrase : ce qui s'est passé, pourquoi, et la conséquence.*

---

## 2. Impact

### Impact utilisateur

| Utilisateurs | Impact | Durée |
|-------------|--------|:-----:|
| *Tous* / *Admins* / *Groupe spécifique* | *Description de ce qu'ils ont expérimenté* | *Durée* |

### Impact technique

| Service | Avant incident | Pendant incident | Après résolution |
|---------|:---:|:---:|:---:|
| `odysseus` | ✓ | ✗ | ✓ |
| `agentos-engine` | ✓ | ✗ | ✓ |
| `chromadb` | ✓ | ✓ | ✓ |
| *[autres]* | | | |

### Données perdues

| Type de données | Quantité | Récupérable ? |
|----------------|:--------:|:-------------:|
| *Sessions in-memory* | *X sessions* | Non |
| *Données persistées* | *Description* | Oui / Non / Partiel |

---

## 3. Timeline

*Heures en UTC. Inclure les actions, observations, et communications.*

| Heure (UTC) | Événement | Source |
|:-----------:|-----------|--------|
| HH:MM | *Premier signal d'alerte* | *Healthcheck* |
| HH:MM | *Action entreprise* | *Qui a fait quoi* |
| HH:MM | *Hypothèse formulée* | *"On pense que c'est X parce que Y"* |
| HH:MM | *Découverte de la cause racine* | *Logs / analyse* |
| HH:MM | *Correctif appliqué* | *Commande ou PR* |
| HH:MM | *Service restauré* | *Healthcheck OK* |
| HH:MM | *Communication aux utilisateurs* | *Canal* |

---

## 4. Analyse de la cause racine (5 Whys)

### Problème initial

*Énoncer le problème tel qu'observé : "Le conteneur agentos-engine a redémarré en boucle."*

### Why #1

Pourquoi le conteneur a-t-il redémarré en boucle ?

> *Réponse*

### Why #2

Pourquoi [réponse #1] ?

> *Réponse*

### Why #3

Pourquoi [réponse #2] ?

> *Réponse*

### Why #4

Pourquoi [réponse #3] ?

> *Réponse*

### Why #5

Pourquoi [réponse #4] ?

> *Réponse*

### Cause racine

*Synthèse de la cause fondamentale identifiée par l'analyse des 5 Whys. Distinguer la cause racine des symptômes.*

---

## 5. Ce qui a bien fonctionné

*Reconnaître ce qui a bien marché pendant l'incident. C'est un post-mortem blameless.*

- ✅ *L'alerte ntfy a été reçue en < 30 secondes*
- ✅ *Le fallback legacy dans opencode_bridge.py a maintenu le service partiellement fonctionnel*
- ✅ *Le workflow security-incident.yaml a automatiquement capturé les logs et le snapshot DB*
- ✅ *Le rollback a été exécuté en < 15 minutes*
- ✅ *La communication a été claire et fréquente*

---

## 6. Ce qui n'a pas fonctionné

*Identifier les défaillances sans blâmer les individus. Se concentrer sur les processus, outils, et systèmes.*

- ❌ *Le healthcheck Docker n'a pas détecté le problème avant 5 minutes (intervalle trop long)*
- ❌ *L'alerte ntfy est arrivée 10 minutes après le healthcheck KO (latence du pipeline)*
- ❌ *Aucune documentation n'expliquait comment redémarrer l'engine isolé*
- ❌ *Le mode legacy était cassé suite à une modification non testée*
- ❌ *Aucun test automatisé ne couvrait ce scénario de panne*

---

## 7. Actions correctives

*Chaque action doit avoir un propriétaire et une date d'échéance. Priorité : P0 (immédiat), P1 (cette semaine), P2 (ce mois).*

| ID | Action | Type | Priorité | Propriétaire | Échéance | Statut |
|:--:|--------|------|:--------:|-------------|:--------:|:------:|
| AC-01 | *Réduire l'intervalle du healthcheck docker de 30s à 15s* | Prévention | P0 | @admin | AAAA-MM-JJ | ⬜ |
| AC-02 | *Ajouter un test d'intégration pour le scénario de panne de l'engine* | Détection | P0 | @dev | AAAA-MM-JJ | ⬜ |
| AC-03 | *Créer un runbook "Redémarrage de l'agentos-engine"* | Documentation | P1 | @dev | AAAA-MM-JJ | ⬜ |
| AC-04 | *Corriger le fallback legacy dans opencode_bridge.py* | Correction | P1 | @dev | AAAA-MM-JJ | ⬜ |
| AC-05 | *Ajouter un circuit breaker pour éviter les boucles de redémarrage* | Prévention | P1 | @dev | AAAA-MM-JJ | ⬜ |
| AC-06 | *Mettre en place un test de chaos engineering mensuel* | Prévention | P2 | @admin | AAAA-MM-JJ | ⬜ |

### Classification des actions

| Type | Définition |
|------|-----------|
| **Correction** | Corrige la cause racine identifiée |
| **Détection** | Améliore la capacité à détecter ce type d'incident plus rapidement |
| **Prévention** | Empêche que ce type d'incident ne se reproduise |
| **Documentation** | Améliore la documentation pour faciliter la résolution future |
| **Processus** | Améliore les processus de réponse aux incidents |

---

## 8. Leçons apprises

### Pour l'équipe

1. *Leçon 1 : description de ce qu'on a appris*
2. *Leçon 2 : description*
3. *Leçon 3 : description*

### Pour le système

1. *Leçon 1 : ce qui doit changer dans l'architecture ou la configuration*
2. *Leçon 2 : ce qui doit changer*

### Pour la documentation

1. *Document à créer ou mettre à jour*
2. *Document à créer ou mettre à jour*

---

## 9. Annexe

### Logs pertinents

```
[Insérer les extraits de logs pertinents — anonymisés si nécessaire]
```

### Métriques

- **Temps de détection (TTD)** : *X minutes*
- **Temps de réponse (TTR)** : *X minutes*
- **Temps de résolution (TTM)** : *X minutes*
- **Comparaison avec SLA** : *RTO respecté ? RPO respecté ?*

### Captures d'écran / Graphiques

*[Liens vers des captures LangFuse, Grafana, ou captures d'écran du Cockpit]*

---

## Signature

Ce rapport est rédigé dans un esprit **blameless**. L'objectif est d'apprendre et d'améliorer le système, pas d'attribuer des fautes.

| Rôle | Nom | Date |
|------|------|------|
| Auteur du rapport | | |
| Reviewé par | | |
| Actions correctives validées par | | |
