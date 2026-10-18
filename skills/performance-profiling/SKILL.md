---
name: performance-profiling
description: Measures system performance — TTFT, TPS, latency, memory. Feeds cockpit with live metrics. Integrated into BUILD and QUALITY phases.
category: quality
tags: [performance, profiling, latency, metrics, monitoring]
platforms: [python, docker]
when_to_use: "Automatique à chaque run BUILD/QUALITY, ou quand l'utilisateur demande 'est-ce que c'est rapide ?'"
procedure:
  - Collect TTFT (Time To First Token) from SSE metrics
  - Collect TPS (Tokens Per Second) from SSE metrics
  - Measure endpoint latency (p50, p95)
  - Track memory usage (Docker stats)
  - Compare against baseline (previous run)
  - Alert if degradation > 30%
verification:
  - TTFT < 3s (acceptable), < 1s (optimal)
  - TPS > 20 (acceptable), > 50 (optimal)
  - Memory < 2GB (container)
confidence: 0.95
---

## What it measures

| Metric | Source | Where shown |
|--------|--------|-------------|
| TTFT (Time To First Token) | SSE events: `metrics.time_to_first_token` | Cockpit chip |
| TPS (Tokens Per Second) | SSE events: `metrics.tokens_per_second` | Cockpit chip |
| Endpoint latency | Profiler wrapper on API calls | Event bus |
| Memory usage | Docker stats API | Cockpit chip |
| Context window % | `metrics.context_percent` | Cockpit chip |
| Model used | `metrics.model` | Cockpit chip |

## Baselines (stockées dans Obsidian vault)
```yaml
# obsidian-vault/topics/performance.md
- [observed] minimax-m3: TTFT=1.68s, TPS=54.88 (baseline 2026-07-28)
- [observed] deepseek-v4-pro: TTFT=2.1s, TPS=45.2 (baseline 2026-07-27)
```

## Alert thresholds
| Condition | Severity | Action |
|-----------|----------|--------|
| TTFT > 5s | Warning | Notify cockpit |
| TTFT > 10s | Error | Fallback model |
| TPS < 10 | Warning | Notify cockpit |
| Memory > 80% | Error | Compact session |
| Degradation > 30% | Warning | Auto-evolve investigate |

## Integration
- **Phase:** BUILD + QUALITY (collecte continue)
- **Event:** `perf_latency`, `perf_memory`, `perf_degradation`
- **Cockpit:** Nouveau chip "Performance" (TTFT, TPS, RAM)
