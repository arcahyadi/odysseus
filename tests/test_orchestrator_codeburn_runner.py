"""Tests for CodeBurn runner — kill-switch gating, CLI invocation, observer feeding."""

import os
from unittest.mock import AsyncMock, MagicMock, patch


# ── kill-switch tests ────────────────────────────────────────────────
class TestCodeBurnEnabled:
    def test_off_by_default(self):
        from src.orchestrator.codeburn_runner import codeburn_enabled

        with patch.dict(os.environ, {}, clear=True):
            assert codeburn_enabled() is False

    def test_on(self):
        from src.orchestrator.codeburn_runner import codeburn_enabled

        with patch.dict(os.environ, {"ODYSSEUS_CODEBURN": "on"}):
            assert codeburn_enabled() is True

    def test_off_explicit(self):
        from src.orchestrator.codeburn_runner import codeburn_enabled

        with patch.dict(os.environ, {"ODYSSEUS_CODEBURN": "off"}):
            assert codeburn_enabled() is False


# ── runner tests ─────────────────────────────────────────────────────
class TestRunCodeBurn:
    def test_disabled_returns_empty(self):
        from src.orchestrator.codeburn_runner import run_codeburn

        with patch.dict(os.environ, {}, clear=True):
            import asyncio

            result = asyncio.run(run_codeburn("test"))
            assert result == {}

    def test_no_cli_returns_empty(self):
        from src.orchestrator.codeburn_runner import run_codeburn

        with patch.dict(os.environ, {"ODYSSEUS_CODEBURN": "on"}):
            with patch("src.orchestrator.codeburn_runner._find_codeburn", return_value=None):
                import asyncio

                result = asyncio.run(run_codeburn("test"))
                assert result == {}

    def test_no_trace_dir_returns_empty(self):
        from src.orchestrator.codeburn_runner import run_codeburn

        with patch.dict(os.environ, {"ODYSSEUS_CODEBURN": "on"}):
            with patch("src.orchestrator.codeburn_runner._find_codeburn", return_value="codeburn"):
                with patch("src.orchestrator.codeburn_runner.Path.exists", return_value=False):
                    import asyncio

                    result = asyncio.run(run_codeburn("test"))
                    assert result == {}

    def test_successful_run(self):
        from src.orchestrator.codeburn_runner import run_codeburn

        fake_report = {
            "oneShotRate": 0.85,
            "wastePatterns": [{"name": "read_loop", "tokens": 500}],
            "costVsCommits": {"abc123": 0.02},
            "touchedFiles": ["src/main.py"],
            "grade": "B",
        }
        import json

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(json.dumps(fake_report).encode(), b""))

        with patch.dict(os.environ, {"ODYSSEUS_CODEBURN": "on"}):
            with patch("src.orchestrator.codeburn_runner._find_codeburn", return_value="codeburn"):
                with patch("src.orchestrator.codeburn_runner.Path.exists", return_value=True):
                    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                        import asyncio

                        result = asyncio.run(run_codeburn("test"))
                        assert result["one_shot_rate"] == 0.85
                        assert len(result["waste_patterns"]) == 1
                        assert result["grade"] == "B"

    def test_cli_failure_returns_empty(self):
        from src.orchestrator.codeburn_runner import run_codeburn

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))

        with patch.dict(os.environ, {"ODYSSEUS_CODEBURN": "on"}):
            with patch("src.orchestrator.codeburn_runner._find_codeburn", return_value="codeburn"):
                with patch("src.orchestrator.codeburn_runner.Path.exists", return_value=True):
                    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                        import asyncio

                        result = asyncio.run(run_codeburn("test"))
                        assert result == {}

    def test_timeout_returns_empty(self):
        from src.orchestrator.codeburn_runner import run_codeburn

        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(side_effect=TimeoutError())

        with patch.dict(os.environ, {"ODYSSEUS_CODEBURN": "on"}):
            with patch("src.orchestrator.codeburn_runner._find_codeburn", return_value="codeburn"):
                with patch("src.orchestrator.codeburn_runner.Path.exists", return_value=True):
                    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                        import asyncio

                        result = asyncio.run(run_codeburn("test"))
                        assert result == {}


# ── observer feeding tests ───────────────────────────────────────────
class TestFeedObserver:
    def test_empty_report_noop(self):
        from src.orchestrator.codeburn_runner import feed_observer

        # Should not raise
        feed_observer({})

    def test_feeds_observer(self):
        from src.observer import Observer
        from src.orchestrator.codeburn_runner import feed_observer

        report = {
            "one_shot_rate": 0.9,
            "waste_patterns": [],
            "touched_files": [],
            "grade": "A",
        }
        observer = Observer()
        initial_count = len(observer._codeburn_reports)
        feed_observer(report)
        assert len(observer._codeburn_reports) == initial_count + 1

    def test_harness_touched_detected(self):
        from src.observer import Observer
        from src.orchestrator.codeburn_runner import feed_observer

        report = {
            "one_shot_rate": 0.5,
            "waste_patterns": [],
            "touched_files": ["src/agent_loop.py", "config/phase-lock.yaml"],
            "grade": "C",
        }
        observer = Observer()
        feed_observer(report)
        # observer._harness_touched should be True because agent_loop.py is a harness file
        assert observer._harness_touched is True
