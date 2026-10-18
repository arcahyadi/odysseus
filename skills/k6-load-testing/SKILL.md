---
name: k6-load-testing
description: Load/stress/soak testing with k6 — validates system behavior under load. Integrated into AUTOEVAL phase.
category: quality
tags: [load-testing, performance, k6, stress-test]
platforms: [web, api]
when_to_use: "Before release majeure, après déploiement, ou quand l'utilisateur demande un test de charge"
procedure:
  - Define test scenario (virtual users, duration, ramp-up)
  - Execute k6 test against target endpoints
  - Collect metrics: p95/p99 latency, error rate, throughput
  - Compare against baseline (previous run)
  - Alert if degradation > 20%
  - Generate HTML report
verification:
  - p95 latency < target SLA
  - Error rate < 1%
  - No memory leaks (soak test 10min)
confidence: 0.9
---

## Test types
| Type | VUs | Duration | When |
|------|-----|----------|------|
| Smoke | 5 | 30s | Every deploy |
| Load | 50 | 5min | Before release |
| Stress | 200 | 3min | Before major launch |
| Soak | 30 | 10min | Weekly |

## Metrics collected
- `http_req_duration` (p50, p95, p99, max)
- `http_req_failed` (error rate %)
- `http_reqs` (throughput)
- `iterations` (total requests)
- Custom: `tokens_per_second`, `memory_usage`

## Endpoints à tester
- `GET /api/health` — baseline
- `POST /api/chat_stream` — charge réelle (mode agent)
- `GET /api/knowledge/status` — Trinité
- `GET /api/agents` — catalogue agents

## Intégration
- **Phase:** AUTOEVAL (après QUALITY)
- **Docker:** service k6 dans docker-compose
- **Event:** `load_test_start`, `load_test_result`
- **Cockpit:** chip performance metrics
