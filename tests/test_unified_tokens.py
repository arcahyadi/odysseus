"""M3.X — unified token accounting (single writer of truth).

Tokens were counted in ~5 places with no single source of truth (cartography
risk #1). The authoritative writer is the final metrics dict produced by
`_compute_final_metrics` (lands in chat_messages.meta_data), stamped with a
per-run `run_id` (commit 18c37f9). This slice lets secondary writers reconcile
against those authoritative per-run totals instead of independently writing
divergent numbers.

Everything is behind a default-OFF kill-switch `ODYSSEUS_UNIFIED_TOKENS`
(mirrors phase_tracker.tracker_enabled). When OFF, behaviour is byte-identical
to today. Best-effort: token accounting must never raise into the agent loop.
"""

import pytest

from src import trace_writer

# ---------------------------------------------------------------------------
# Kill-switch
# ---------------------------------------------------------------------------


def test_unified_tokens_enabled_by_default(monkeypatch):
    """Palier 0 (FND-4 option C): UNIFIED_TOKENS is ON by default again.

    The OFF polarity is still covered right below: a kill-switch nobody
    can turn off is not a kill-switch.
    """
    monkeypatch.delenv("ODYSSEUS_UNIFIED_TOKENS", raising=False)
    assert trace_writer.unified_tokens_enabled() is True


def test_unified_tokens_can_be_off(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_UNIFIED_TOKENS", "off")
    assert trace_writer.unified_tokens_enabled() is False


@pytest.mark.parametrize("val", ["on", "1", "true", "yes", "ON", "Yes", " true "])
def test_unified_tokens_enabled_for_truthy_values(monkeypatch, val):
    monkeypatch.setenv("ODYSSEUS_UNIFIED_TOKENS", val)
    assert trace_writer.unified_tokens_enabled() is True


@pytest.mark.parametrize("val", ["off", "0", "false", "no", "", "nope"])
def test_unified_tokens_disabled_for_falsy_values(monkeypatch, val):
    monkeypatch.setenv("ODYSSEUS_UNIFIED_TOKENS", val)
    assert trace_writer.unified_tokens_enabled() is False


# ---------------------------------------------------------------------------
# Authoritative per-run token registry (writer of truth publishes here)
# ---------------------------------------------------------------------------


def test_record_and_get_run_tokens_roundtrip():
    trace_writer.record_run_tokens("run-x", input_tokens=100, output_tokens=42)
    got = trace_writer.get_run_tokens("run-x")
    assert got == {"input_tokens": 100, "output_tokens": 42}


def test_get_run_tokens_unknown_returns_none():
    assert trace_writer.get_run_tokens("does-not-exist") is None


def test_record_run_tokens_last_write_wins_for_same_run():
    # _compute_final_metrics is the single writer of truth: the final metrics
    # dict holds the authoritative TOTAL for the run, so re-recording overwrites
    # (it does not accumulate a second time).
    trace_writer.record_run_tokens("run-y", input_tokens=10, output_tokens=5)
    trace_writer.record_run_tokens("run-y", input_tokens=30, output_tokens=9)
    assert trace_writer.get_run_tokens("run-y") == {
        "input_tokens": 30,
        "output_tokens": 9,
    }


def test_record_run_tokens_never_raises_on_bad_input():
    # best-effort: must not blow up the loop even with junk
    trace_writer.record_run_tokens(None, input_tokens="bad", output_tokens=None)
    # no assertion on stored value — the contract is "does not raise"


# ---------------------------------------------------------------------------
# accumulate_token_usage reconciliation (secondary writer)
# ---------------------------------------------------------------------------


class _FakeSession:
    """Minimal DBSession row stand-in."""

    def __init__(self, sid):
        self.id = sid
        self.total_input_tokens = 0
        self.total_output_tokens = 0


class _FakeQuery:
    def __init__(self, row):
        self._row = row

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._row


class _FakeDB:
    def __init__(self, row):
        self._row = row
        self.committed = False

    def query(self, *a, **k):
        return _FakeQuery(self._row)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


@pytest.fixture
def patched_helpers(monkeypatch):
    from routes import chat_helpers

    row = _FakeSession("sess-1")
    fake_db = _FakeDB(row)
    monkeypatch.setattr(chat_helpers, "SessionLocal", lambda: fake_db)
    return chat_helpers, row, fake_db


def test_accumulate_off_uses_metrics_dict_as_today(monkeypatch, patched_helpers):
    """Kill-switch OFF: byte-identical to today — trusts the passed dict,
    never consults the authoritative registry."""
    chat_helpers, row, _ = patched_helpers
    monkeypatch.setenv("ODYSSEUS_UNIFIED_TOKENS", "off")

    # Poison the registry with different numbers; OFF path must ignore it.
    trace_writer.record_run_tokens("run-off", input_tokens=999, output_tokens=999)

    chat_helpers.accumulate_token_usage("sess-1", {"input_tokens": 7, "output_tokens": 3, "run_id": "run-off"})
    assert row.total_input_tokens == 7
    assert row.total_output_tokens == 3


def test_accumulate_on_reconciles_against_authoritative_totals(monkeypatch, patched_helpers):
    """Kill-switch ON: secondary writer uses the authoritative per-run totals
    (correlated by run_id) instead of the divergent numbers in the dict."""
    chat_helpers, row, _ = patched_helpers
    monkeypatch.setenv("ODYSSEUS_UNIFIED_TOKENS", "on")

    # Writer of truth published these; the dict carries stale/divergent values.
    trace_writer.record_run_tokens("run-on", input_tokens=120, output_tokens=40)

    chat_helpers.accumulate_token_usage("sess-1", {"input_tokens": 5, "output_tokens": 1, "run_id": "run-on"})
    assert row.total_input_tokens == 120
    assert row.total_output_tokens == 40


def test_accumulate_on_without_run_id_falls_back_to_dict(monkeypatch, patched_helpers):
    """ON but no run_id in metrics: nothing to reconcile against, so fall back
    to the dict values (never lose accounting)."""
    chat_helpers, row, _ = patched_helpers
    monkeypatch.setenv("ODYSSEUS_UNIFIED_TOKENS", "on")

    chat_helpers.accumulate_token_usage("sess-1", {"input_tokens": 8, "output_tokens": 2})
    assert row.total_input_tokens == 8
    assert row.total_output_tokens == 2


def test_accumulate_on_unknown_run_id_falls_back_to_dict(monkeypatch, patched_helpers):
    """ON with a run_id the registry never saw: fall back to dict values."""
    chat_helpers, row, _ = patched_helpers
    monkeypatch.setenv("ODYSSEUS_UNIFIED_TOKENS", "on")

    chat_helpers.accumulate_token_usage("sess-1", {"input_tokens": 6, "output_tokens": 4, "run_id": "never-seen"})
    assert row.total_input_tokens == 6
    assert row.total_output_tokens == 4
