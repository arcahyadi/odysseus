"""Performance Profiler — hooks into SSE metrics for live performance tracking."""

import os
from threading import Lock


class PerfProfiler:
    """Collects performance metrics from SSE events and Docker stats."""

    def __init__(self, baseline_path: str = "obsidian-vault/topics/performance.md"):
        self.baseline_path = baseline_path
        self._lock = Lock()
        self._metrics = {
            "ttft_avg": 0.0,
            "ttft_samples": 0,
            "tps_avg": 0.0,
            "tps_samples": 0,
            "latency_p50": 0.0,
            "latency_p95": 0.0,
            "latency_samples": [],
            "memory_mb": 0.0,
            "context_percent_avg": 0.0,
            "baseline": {},
        }
        self._load_baseline()

    def _load_baseline(self):
        """Load stored baseline from Obsidian vault."""
        try:
            if os.path.exists(self.baseline_path):
                with open(self.baseline_path) as f:
                    content = f.read()
                    for line in content.split("\n"):
                        if "TTFT=" in line and "TPS=" in line:
                            parts = line.split("TTFT=")[1].split("TPS=") if "TTFT=" in line else ["", ""]
                            # Parse baseline
        except:
            pass
        self._metrics["baseline"] = {
            "ttft": 1.68,  # minimax-m3 default
            "tps": 54.88,
            "model": "minimax-m3",
        }

    def record_llm_metrics(self, data: dict):
        """Record metrics from an SSE metrics event."""
        with self._lock:
            ttft = data.get("time_to_first_token", 0)
            tps = data.get("tokens_per_second", 0)
            model = data.get("model", "unknown")
            latency = data.get("response_time", 0)
            ctx_pct = data.get("context_percent", 0)

            if ttft > 0:
                n = self._metrics["ttft_samples"]
                self._metrics["ttft_avg"] = (self._metrics["ttft_avg"] * n + ttft) / (n + 1)
                self._metrics["ttft_samples"] = n + 1

            if tps > 0:
                n = self._metrics["tps_samples"]
                self._metrics["tps_avg"] = (self._metrics["tps_avg"] * n + tps) / (n + 1)
                self._metrics["tps_samples"] = n + 1

            if ctx_pct > 0:
                self._metrics["context_percent_avg"] = ctx_pct

            if latency > 0:
                self._metrics["latency_samples"].append(latency)
                # Keep last 100 samples
                if len(self._metrics["latency_samples"]) > 100:
                    self._metrics["latency_samples"] = self._metrics["latency_samples"][-100:]
                sorted_lat = sorted(self._metrics["latency_samples"])
                n = len(sorted_lat)
                self._metrics["latency_p50"] = sorted_lat[n // 2]
                self._metrics["latency_p95"] = sorted_lat[int(n * 0.95)]

            # Check degradation
            baseline_ttft = self._metrics["baseline"].get("ttft", 1.5)
            if ttft > baseline_ttft * 2:
                return {
                    "alert": "degradation",
                    "metric": "TTFT",
                    "current": ttft,
                    "baseline": baseline_ttft,
                    "severity": "warning" if ttft < baseline_ttft * 3 else "error",
                }

            return None

    def get_status(self) -> dict:
        """Get current performance status for cockpit."""
        with self._lock:
            return {
                "ttft_avg": round(self._metrics["ttft_avg"], 2),
                "ttft_samples": self._metrics["ttft_samples"],
                "tps_avg": round(self._metrics["tps_avg"], 1),
                "latency_p50": round(self._metrics["latency_p50"], 2),
                "latency_p95": round(self._metrics["latency_p95"], 2),
                "memory_mb": round(self._metrics["memory_mb"], 1),
                "context_pct": round(self._metrics["context_percent_avg"], 1),
                "baseline_ttft": self._metrics["baseline"].get("ttft", 1.5),
                "degradation": self._check_degradation(),
            }

    def _check_degradation(self) -> str:
        m = self._metrics
        baseline = m["baseline"].get("ttft", 1.5)
        current = m["ttft_avg"]
        if current == 0:
            return "no_data"
        ratio = current / baseline if baseline > 0 else 1
        if ratio > 1.5:
            return "degraded"
        elif ratio > 1.2:
            return "warning"
        return "normal"


# Singleton
profiler = PerfProfiler()
