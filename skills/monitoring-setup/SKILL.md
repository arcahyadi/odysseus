# skill: monitoring-setup

## triggers
- demande de monitoring, observabilité, dashboards
- après déploiement, post-livraison
- "configure le monitoring", "active l'observabilité"

## tools
- LangFuse (déjà dans Docker, port 3000, gated ODYSSEUS_LANGFUSE)
- src/trace_writer.py (JSONL traces)
- curl /api/health (health check)
- docker compose ps (service status)

## procedure
1. Activer LangFuse: ODYSSEUS_LANGFUSE=on
2. Vérifier les 3 piliers:
   - Logs: app logs dans logs/
   - Métriques: /api/health, docker stats
   - Traces: JSONL dans data/traces/
3. Configurer les dashboards LangFuse:
   - Coût par projet/phase
   - Latence p50/p95
   - Taux d'erreur
4. Configurer l'alerting:
   - Health endpoint down → notifier
   - Budget > 80% → alerter
   - Taux d'erreur > 5% → alerter
5. Tester une alerte

## constraints
- Éviter l'alert fatigue (pas plus de 3 alertes critiques)
- Les dashboards doivent être actionnables
- NF-07: traces structurées obligatoires
