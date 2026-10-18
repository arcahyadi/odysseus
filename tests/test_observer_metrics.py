"""M3.3 — Observer consumes existing metrics + tool_events (no recompute).

The live observer block created a fresh ``Observer`` each turn but only fed it
the budget status — it never consumed the ``_compute_final_metrics`` output or
the ``tool_events`` already assembled for the SSE stream. Roadmap M3.3: feed the
drift score off those existing signals. ``ingest_metrics`` derives a
CodeBurn-style report (one_shot_rate, waste_patterns, touched_files) from the
tool events and reuses the existing drift machinery — writes to harness files
still escalate to HIGH; reads (e.g. ``cat`` via bash) do not.
"""

from src.observer import DriftLevel, Observer, reset_observer_state


def test_clean_run_is_low_drift():
    reset_observer_state()
    reset_observer_state()
    obs = Observer()
    obs.ingest_metrics(
        {},
        tool_events=[
            {"tool": "bash", "command": "ls", "exit_code": 0},
            {"tool": "python", "command": "print(1)", "exit_code": 0},
        ],
    )
    assert obs.compute_drift_score() == DriftLevel.LOW


def test_three_failed_tools_is_medium_drift():
    reset_observer_state()
    reset_observer_state()
    obs = Observer()
    obs.ingest_metrics(
        {},
        tool_events=[
            {"tool": "bash", "command": "a", "exit_code": 1},
            {"tool": "bash", "command": "b", "exit_code": 2},
            {"tool": "bash", "command": "c", "exit_code": 1},
        ],
    )
    assert obs.compute_drift_score() == DriftLevel.MEDIUM


def test_harness_write_escalates_to_high():
    reset_observer_state()
    obs = Observer()
    obs.ingest_metrics(
        {},
        tool_events=[
            {"tool": "write_file", "command": "src/agent_loop.py\n<content>", "exit_code": 0},
        ],
    )
    assert obs.compute_drift_score() == DriftLevel.HIGH


def test_harness_read_via_bash_is_not_flagged():
    reset_observer_state()
    obs = Observer()
    obs.ingest_metrics(
        {},
        tool_events=[
            {"tool": "bash", "command": "cat src/agent_loop.py", "exit_code": 0},
        ],
    )
    assert obs.compute_drift_score() == DriftLevel.LOW


def test_no_tool_events_is_low_drift():
    reset_observer_state()
    obs = Observer()
    obs.ingest_metrics({}, tool_events=[])
    assert obs.compute_drift_score() == DriftLevel.LOW
    obs.ingest_metrics({})  # nothing in metrics either
    assert obs.compute_drift_score() == DriftLevel.LOW


def test_pulls_tool_events_from_metrics_when_arg_omitted():
    reset_observer_state()
    obs = Observer()
    obs.ingest_metrics({"tool_events": [{"tool": "bash", "command": "x", "exit_code": 1}]})
    summary = obs.get_summary()
    assert summary["codeburn_reports_count"] == 1


def test_derives_one_shot_rate_and_waste_patterns():
    reset_observer_state()
    obs = Observer()
    obs.ingest_metrics(
        {},
        tool_events=[
            {"tool": "bash", "command": "ok", "exit_code": 0},
            {"tool": "bash", "command": "boom", "exit_code": 1},
        ],
    )
    summary = obs.get_summary()
    assert summary["latest_codeburn_one_shot_rate"] == 0.5
    # exactly one failed event → one waste pattern
    assert obs.compute_drift_score() == DriftLevel.MEDIUM


def test_none_exit_code_counts_as_success():
    reset_observer_state()
    obs = Observer()
    obs.ingest_metrics(
        {},
        tool_events=[
            {"tool": "edit_document", "command": "note", "exit_code": None},
            {"tool": "edit_document", "command": "note2", "exit_code": None},
        ],
    )
    assert obs.get_summary()["latest_codeburn_one_shot_rate"] == 1.0
    assert obs.compute_drift_score() == DriftLevel.LOW
