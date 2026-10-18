# skill: visual-output

## triggers
- demande de diagramme, graphique, schéma, visualisation
- "montre-moi", "visualise", "diagramme", "graphique", "illustre"
- architecture système, flux de données, comparaison

## tools
- Kroki (MCP, déjà dans Docker) — Mermaid, PlantUML, GraphViz
- src/visual_output/ (router, renderer, 6 design modules)
- HTML/SVG inline dans le flux de conversation

## procedure
1. Détecter si la réponse mérite un visuel (patterns + LLM)
2. Router via OutputRouter.decide(): MCP tool → file → inline visual
3. Si diagramme → utiliser Kroki (Mermaid)
4. Si chart → générer SVG inline
5. Si mockup → HTML/CSS inline
6. Toujours accompagner le visuel de prose
7. Ne jamais empiler des visuels sans texte intercalé

## constraints
- Couleurs: palette du module de design concerné
- Dimensions: max 900x600 par défaut
- Kroki déjà connecté (port 8700)
- Format: SVG pour diagrammes, HTML pour interactifs
