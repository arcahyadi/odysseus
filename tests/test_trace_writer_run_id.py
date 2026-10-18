"""M3.X slice 1 — per-run correlation id in trace_writer.

Before this slice, `run_id` was a process-level constant (one UUID for the
whole process lifetime), so traces from different runs/turns could not be
correlated. These tests pin the new per-run behaviour: a run scope can be
opened with a fresh id, `write_trace` records the *current* id, and the
default (no scope opened) stays backward-compatible with the process id.
"""

import json

import pytest

from src import trace_writer


@pytest.fixture(autouse=True)
def _isolate_run_id():
    """Restore the run_id contextvar after each test."""
    token_before = trace_writer.current_run_id()
    yield
    # Reset to a known process-level id so tests don't leak into each other.
    trace_writer.set_run_id(token_before)


def _read_traces(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_current_run_id_defaults_to_nonempty_uuid():
    rid = trace_writer.current_run_id()
    assert isinstance(rid, str) and len(rid) >= 8


def test_new_run_id_changes_current():
    first = trace_writer.current_run_id()
    fresh = trace_writer.new_run_id()
    assert fresh != first
    assert trace_writer.current_run_id() == fresh


def test_set_run_id_overrides_current():
    trace_writer.set_run_id("run-abc")
    assert trace_writer.current_run_id() == "run-abc"


def test_write_trace_records_current_run_id(tmp_path, monkeypatch):
    fpath = tmp_path / "traces.jsonl"
    monkeypatch.setattr(trace_writer, "_today_file", lambda: fpath)

    rid = trace_writer.new_run_id()
    trace_writer.write_trace(
        tool="bash",
        risk_level="SAFE",
        args_summary="ls",
        permission_decision="auto_approved",
        outcome="success",
        session_id="sess-1",
    )

    records = _read_traces(fpath)
    assert len(records) == 1
    assert records[0]["run_id"] == rid
    assert records[0]["session_id"] == "sess-1"


def test_two_runs_produce_distinct_run_ids_in_traces(tmp_path, monkeypatch):
    fpath = tmp_path / "traces.jsonl"
    monkeypatch.setattr(trace_writer, "_today_file", lambda: fpath)

    rid1 = trace_writer.new_run_id()
    trace_writer.write_trace(
        tool="bash",
        risk_level="SAFE",
        args_summary="a",
        permission_decision="auto_approved",
        outcome="success",
    )
    rid2 = trace_writer.new_run_id()
    trace_writer.write_trace(
        tool="bash",
        risk_level="SAFE",
        args_summary="b",
        permission_decision="auto_approved",
        outcome="success",
    )

    records = _read_traces(fpath)
    assert rid1 != rid2
    assert [r["run_id"] for r in records] == [rid1, rid2]
