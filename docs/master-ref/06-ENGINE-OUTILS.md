# Moteur OpenCode & Outils Tiers — Intégration

> **Réf :** 02-OUTILS-TIERS (60 outils) + 01-SFD (20 modules, 7 phases)

---

## Architecture Cible

```
Odysseus UI (allégée) ──→ OpenCode Engine ──→ ZenRouter ──→ LLM
                              │
                              ├── Agents (.opencode/) dispatchés par phase
                              ├── Skills (.opencode/skills/) chargés avant tâche
                              ├── Plugins (@agentos/sfd-*) hooks sur event bus
                              ├── MCP servers (Kroki, Scrapling, Serena...)
                              └── Event Bus → UI + traces + alertes
```

---

## Outils Tiers par Phase SFD

D'après l'analyse des 60 outils (02-OUTILS-TIERS) :

### CLASSIFY — Évaluation risque
| Outil | Rôle | Statut |
|-------|------|--------|
| **Paperclip** (governance) | goal-ancestry, budgets auto-pause | 📋 Absorber patterns |
| **HexStrike** (permission matrix) | sandbox + permission validation | 📋 Pattern absorbé |

### KNOW — Recherche & Contexte
| Outil | Rôle | Statut |
|-------|------|--------|
| **CBM** (codebase-memory) | Graphe de code (11K nœuds) | ✅ Intégré (MCP) |
| **Graphify** | Graphe sémantique concepts | ✅ Intégré (MCP) |
| **Serena MCP** | Code intelligence LSP | ✅ Intégré (Docker) |
| **Meilisearch** | Full-text search | ✅ Intégré (Docker) |

### PLAN — Décomposition
| Outil | Rôle | Statut |
|-------|------|--------|
| **OmO** (tiered routing) | Router modèle par complexité | 📋 Pattern absorbé (ZenRouter) |
| **Caveman Method** | Standard obligatoire, eval figée | 📋 Pattern absorbé |

### BUILD — Exécution
| Outil | Rôle | Statut |
|-------|------|--------|
| **Scrapling MCP** | Web scraping adaptatif | ✅ Intégré (Docker) |
| **Kroki** | Diagrammes Mermaid/PlantUML | ✅ Intégré (Docker) |
| **Serena** | Édition sémantique LSP | ✅ Intégré (Docker) |
| **Faker.js** | Données de test | 👀 Veille |
| **Supabase MCP** | DB branching + state agents | 📋 Planifié |

### QUALITY — Vérification
| Outil | Rôle | Statut |
|-------|------|--------|
| **CodeBurn** | One-shot rate, waste patterns | ✅ Intégré |
| **vibecode** (quality pipeline) | Phase-locking, debate, drift | 📋 Pattern absorbé |
| **AgentSeal** | Probes sécurité injection | ✅ Intégré |

### AUTOEVAL — Auto-évaluation
| Outil | Rôle | Statut |
|-------|------|--------|
| **AutoResearch** (Karpathy) | Keep/revert loop | 📋 Pattern absorbé |
| **Autoeval** (existant) | Score vs critères | ✅ Existant (gated) |

### MEMORY_OBSERVE — Apprentissage
| Outil | Rôle | Statut |
|-------|------|--------|
| **Acontext** | Distillation run→SKILL.md | ✅ Intégré (externe) |
| **Obsidian MCP** | Second-brain markdown | ✅ Intégré (gated) |
| **agents-best-practices** | 15 références de skills | 📋 Pattern absorbé |

---

## Outils NON intégrés — Décision

| Outil | Verdict | Raison |
|-------|---------|--------|
| **n8n** | ❌ Retiré | Remplacé par Decision Engine |
| **ANUS** | ❌ Ignoré | 3⭐, pas mature |
| **AppFlowy** | ❌ Ignoré | Redondant avec Notes existant |
| **Napkin AI** | ❌ Ignoré | Pas d'API |
| **Kling AI** | ❌ Ignoré | Vidéo, hors scope |
| **SurfSense** | 👀 Veille | Alternative NotebookLM |
| **Plausible** | 🏦 Banque | Analytics (future) |
| **Chatwoot** | 🏦 Banque | Support client (future) |

---

## Comment OpenCode Engine utilise ces outils

```python
# src/opencode_engine.py — version enrichie

class OpenCodeEngine:
    def get_tools_for_phase(self, phase: str) -> list[str]:
        """Outils MCP disponibles par phase."""
        return {
            "CLASSIFY": [],
            "KNOW":     ["mcp__cbm__search_graph", "mcp__graphify__query", "mcp__serena__references"],
            "PLAN":     [],
            "BUILD":    ["mcp__scrapling__fetch", "mcp__kroki__render", "BASH", "WRITE_FILE"],
            "QUALITY":  ["codeburn", "agentseal"],
            "AUTOEVAL": [],
            "MEMORY_OBSERVE": ["mcp__obsidian__create_note"],
        }.get(phase, [])

    def get_agents_for_phase(self, phase: str) -> list[str]:
        """Agents OpenCode dispatchés par phase."""
        return {
            "CLASSIFY": ["constitution"],
            "KNOW":     ["explore"],
            "PLAN":     ["planner", "gsd-researcher"],
            "BUILD":    ["executor", "gsd-executor"],
            "QUALITY":  ["reviewer", "security-audit"],
            "AUTOEVAL": ["gsd-verifier"],
            "MEMORY_OBSERVE": ["gsd-roadmapper"],
        }.get(phase, [])
```
