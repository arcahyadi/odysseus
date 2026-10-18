---
name: design-extract
description: >
  Extrait un design system complet depuis une URL avec designlang.
  Tokens DTCG, Tailwind, shadcn theme. Audit CSS + anti-drift.
---

# Design Extract Agent

Extrait un design system complet depuis une URL avec `designlang`.

## Quand utiliser

Quand tu dois recréer ou adapter un design existant, ou générer des tokens CSS depuis un site de référence.

## Capacités

- `designlang extract <url>` → tokens DTCG + Tailwind + shadcn theme
- `designlang grade <url>` → CSS health audit (A-F + WCAG)
- `designlang clone <url>` → genère une app Next.js clonant le design
- `designlang drift <url>` → vérifie que les tokens n'ont pas dérivé

## Prérequis

```bash
npm i -g designlang
designlang --version
```

## Workflow standard

1. `designlang extract <url> --output tokens/`
2. Review des tokens générés (primitive/semantic/composite)
3. `designlang grade <url>` pour vérifier la qualité CSS
4. Appliquer avec `designlang apply --project .`

## Output format

Les tokens suivent DTCG (Design Token Community Group) — compatibles Figma, Tailwind v4, shadcn.
