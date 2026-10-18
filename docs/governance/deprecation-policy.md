# Politique de Dépréciation — Odysseus AgentOS

**Version :** 1.0
**Date d'effet :** 2026-08-06
**Propriétaire :** Équipe Odysseus AgentOS

---

## 1. Principes généraux

1. **Aucune suppression sans préavis.** Aucune fonctionnalité, API, ou service n'est supprimé sans une période de dépréciation documentée.
2. **Migration avant suppression.** Un chemin de migration est fourni avant toute suppression.
3. **Versionnement explicite.** Les changements cassants sont versionnés, jamais silencieux.
4. **Communication multicanal.** Les dépréciations sont annoncées dans le CHANGELOG, les releases GitHub, et les notifications Cockpit.

---

## 2. API Versioning

### 2.1 Stratégie de versionnement

Odysseus utilise un versionnement d'API par URL :

```
/api/v1/chat
/api/v2/chat
```

| Version | Statut | Support |
|---------|--------|---------|
| `/api/v1/` | Actuelle | Support complet |
| `/api/v2/` | Future | Non encore publiée |

### 2.2 Règles de versionnement

| Changement | Nouvelle version ? |
|------------|:---:|
| Ajout d'un endpoint | Non |
| Ajout d'un champ optionnel dans la réponse | Non |
| Ajout d'un paramètre optionnel dans la requête | Non |
| Suppression d'un endpoint | **Oui** |
| Suppression d'un champ de réponse | **Oui** |
| Changement de type d'un champ existant | **Oui** |
| Changement de comportement d'un endpoint existant | **Oui** |
| Changement de format d'erreur | **Oui** |

### 2.3 Cycle de vie d'une version d'API

```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Publiée │───▶│ Dépréciée│───▶│  Sunset  │───▶│ Retirée  │
│ (active)│    │ (warning) │    │ (erreur) │    │ (404)    │
└─────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │                │               │
     │         +1 version          +6 mois        +3 mois
     │         minimum             minimum        minimum
     │
     └── Nouvelle version publiée (vN+1)
```

### 2.4 Délais

| Phase | Durée minimum | Comportement |
|-------|:------------:|--------------|
| **Coexistence** | 1 mois | vN et vN+1 fonctionnent simultanément |
| **Dépréciation** | 6 mois | vN répond normalement mais émet un header `Deprecation: true` et un warning dans les logs |
| **Sunset** | 3 mois | vN répond avec `HTTP 410 Gone` + message de migration |
| **Retrait** | — | vN retourne `HTTP 404` |

**Délai total minimum entre publication de vN+1 et retrait de vN : 10 mois.**

---

## 3. Services Docker

### 3.1 Cycle de vie

| Phase | Préavis | Action utilisateur |
|-------|:-------:|-------------------|
| **Annonce de dépréciation** | 3 mois avant retrait | Aucune (le service continue de fonctionner) |
| **Retrait du profil par défaut** | 1 mois | Migrer vers l'alternative si le service est utilisé |
| **Suppression du docker-compose.yml** | Sur version majeure | Supprimer le service de la configuration locale |

### 3.2 Services actuellement dépréciés

*Aucun service n'est actuellement déprécié.*

### 3.3 Exemple de dépréciation future

Si `chromadb` devait être remplacé par `qdrant` comme vector store par défaut :

```
Mois 1 : Annonce — "ChromaDB sera déplacé vers le profil vectordb-legacy"
Mois 2 : Les deux services cohabitent dans le compose par défaut
Mois 3 : ChromaDB sort du profil par défaut, reste dans vectordb-legacy
Mois 4+ : ChromaDB reste disponible via le profil vectordb-legacy
```

---

## 4. Composants Python

### 4.1 Dépréciation de modules

Quand un module Python est remplacé (ex. `src/agent_loop.py` → `src/opencode_bridge.py`) :

| Phase | Durée | Action |
|-------|:-----:|--------|
| **Annonce** | Immédiate | CHANGELOG + commentaire `@deprecated` dans le code |
| **Coexistence** | 1 version | L'ancien module reste importable mais émet un `DeprecationWarning` |
| **Suppression** | Version majeure suivante | Le module est supprimé |

### 4.2 Exemple de dépréciation

```python
import warnings

def ancienne_fonction():
    """
    @deprecated: Utiliser nouvelle_fonction() à la place.
    Cette fonction sera supprimée dans la v2.0.
    """
    warnings.warn(
        "ancienne_fonction() est dépréciée. Utilisez nouvelle_fonction().",
        DeprecationWarning,
        stacklevel=2
    )
    return nouvelle_fonction()
```

---

## 5. Configuration et variables d'environnement

### 5.1 Dépréciation de variables d'environnement

| Phase | Délai | Comportement |
|-------|:-----:|--------------|
| Annonce | Immédiate | CHANGELOG + `.env.example` mis à jour |
| Warning | 2 versions | L'ancienne variable est lue mais un warning est loggé |
| Suppression | Version majeure | L'ancienne variable est ignorée |

### 5.2 Exemple

Si `ODYSSEUS_OLD_VAR` est remplacée par `ODYSSEUS_NEW_VAR` :

```bash
# Phase 1 : coexistence (v1.x)
# Les deux variables sont lues, OLD_VAR émet un warning

# Phase 2 : suppression (v2.0)
# Seule NEW_VAR est lue
```

---

## 6. Kill-switches

### 6.1 Politique spécifique

Les kill-switches suivent les mêmes règles que les variables d'environnement. Un kill-switch déprécié :

1. Reste fonctionnel pendant 2 versions
2. Émet un warning dans les logs : `Kill-switch ODYSSEUS_OLD_SWITCH is deprecated, use ODYSSEUS_NEW_SWITCH`
3. Est supprimé à la version majeure suivante

### 6.2 Registre des dépréciations

Le registre des kill-switches (`src/killswitch_registry.py:329`) liste les switches actifs. Les switches dépréciés y sont marqués `"status": "deprecated"`.

---

## 7. Plugins npm (@agentos/sfd-*)

### 7.1 Versionnement semver

Les plugins npm suivent le [Semantic Versioning](https://semver.org) :

| Changement | Version |
|------------|---------|
| Correction de bug | **PATCH** (1.0.0 → 1.0.1) |
| Nouvelle fonctionnalité rétrocompatible | **MINOR** (1.0.0 → 1.1.0) |
| Changement cassant | **MAJOR** (1.0.0 → 2.0.0) |

### 7.2 Dépréciation de plugins

Un plugin déprécié :

1. Reste publié sur npm avec un avertissement dans le README
2. Continue de fonctionner pendant 6 mois
3. Est marqué `"deprecated": true` dans son `package.json`
4. Le plugin de remplacement est documenté avec un guide de migration

---

## 8. Communication

### 8.1 Canaux

| Canal | Contenu | Fréquence |
|-------|---------|:---------:|
| **CHANGELOG.md** | Liste de toutes les dépréciations par version | À chaque release |
| **GitHub Releases** | Annonce des dépréciations majeures | À chaque release |
| **Cockpit (UI)** | Bannière d'avertissement si l'instance utilise un composant déprécié | Au démarrage |
| **Logs applicatifs** | Warnings de dépréciation au runtime | À chaque utilisation |
| **Headers HTTP** | `Deprecation: true` + `Sunset: <date>` sur les endpoints dépréciés | À chaque requête |
| **GitHub Issues** | Issue dédiée pour les dépréciations majeures avec label `deprecation` | À l'annonce |

### 8.2 Template d'annonce de dépréciation

```markdown
## Dépréciation : [Composant] → [Remplacement]

**Date d'annonce :** AAAA-MM-JJ
**Date de sunset :** AAAA-MM-JJ
**Date de retrait :** AAAA-MM-JJ

### Ce qui change
[Description du composant déprécié et de son remplacement]

### Pourquoi
[Raison du changement]

### Actions requises
[Étapes de migration]

### Support
[Jusqu'à quelle date le composant déprécié sera supporté]
```

---

## 9. Exceptions

Des dépréciations accélérées sont possibles dans ces cas :

1. **Faille de sécurité critique** : suppression immédiate, préavis de 7 jours maximum
2. **Violation de licence** : suppression immédiate
3. **Service externe arrêté** : sunset aligné sur l'arrêt du service

Toute exception doit être documentée et approuvée par l'équipe de maintenance.

---

## 10. Historique des dépréciations

| Composant | Date annonce | Date sunset | Date retrait | Remplacé par | Statut |
|-----------|:-----------:|:-----------:|:-----------:|-------------|:------:|
| `agent_loop.py` | 2026-07-24 | — | 2026-07-30 | `opencode_bridge.py` | Retiré |
| `llm_core.py` | 2026-07-24 | — | 2026-07-30 | ZenRouter natif OpenCode | Retiré |
| `src/durable_execution/` | 2026-07-24 | — | 2026-07-30 | `@agentos/sfd-durable` | Retiré |
| `src/memory_provenance/` | 2026-07-24 | — | 2026-07-30 | `@agentos/sfd-memory` | Retiré |
| `src/preferences/` | 2026-07-24 | — | 2026-07-30 | `@agentos/sfd-prefs` | Retiré |
| `src/visual_output/` | 2026-07-24 | — | 2026-07-30 | `@agentos/sfd-visual` | Retiré |
| `src/classification/` | 2026-07-24 | — | 2026-07-30 | `@agentos/sfd-classify` | Retiré |
| `src/content_security/` | 2026-07-24 | — | 2026-07-30 | `@agentos/sfd-security` | Retiré |
| `src/tool_discovery/` | 2026-07-24 | — | 2026-07-30 | `@agentos/sfd-discovery` | Retiré |
