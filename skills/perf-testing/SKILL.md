# skill: perf-testing

## triggers
- demande de test de performance, load testing, stress testing
- "teste la performance", "mesure la latence", "benchmark"
- avant mise en production, avant release majeure
- quand NF-01 (<2s) ou NF-02 (10+ projets) doivent être validés

## tools
- k6 (load testing open source) — https://k6.io
- curl + time pour les tests simples
- python -m pytest --timeout pour les timeouts

## procedure
1. Identifier les endpoints critiques (health, chat_stream, version)
2. Lancer un test de charge léger avec k6 ou curl en boucle
3. Mesurer p50, p95, p99
4. Si p95 > 2s → flag NF-01 comme FAIL, suggérer optimisation
5. Si le système tient 10 requêtes simultanées → NF-02 OK
6. Rapporter les résultats dans un tableau

## success criteria
- p95 < 2 secondes pour /api/health
- 10 connexions simultanées sans erreur
- Rapport généré automatiquement
