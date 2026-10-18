---
name: open-design
description: >
  Génère des artefacts de design (composants, dashboards, prototypes)
  depuis un brief texte. 142 design systems, Critique Theater 5 personas.
---

# Open Design Agent

Génère des artefacts de design (composants, dashboards, prototypes) depuis un brief texte.
Utilise Open Design (nexu-io) comme moteur — tourne SUR l'agent courant.

## Quand utiliser

Quand tu dois créer une UI depuis zéro ou adapter un design system existant.

## Installation

```bash
curl -fsSL https://open-design.ai/install.sh | sh -s opencode
```

## Workflow agent-native

1. **Brief** : décris le composant ou l'écran à créer
2. **Direction** : l'agent propose 2-3 directions (validées par Critique Theater)
3. **Artifact** : génère HTML/React/shadcn + tokens
4. **Critique** : 5 critiques auto (Architect/UX/A11y/Performance/Brand)
5. **Deliver** : export HTML/PDF/composants

## Design Systems disponibles

Open Design inclut 142 design systems en DESIGN.md.
Les skills design sont dans `.opencode/skills/design/`.

## Commandes

- Brief simple → composant en 1 round
- `/design review` → Critique Theater sur le dernier artifact
- `/design export` → export HTML/PDF
