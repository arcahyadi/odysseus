"""
tests/phase2/test_temporal.py

Property and unit tests for TemporalMemoryStore.
Requirements: 1.1-1.9, 2.1-2.4 (phase 2)

# Feature: phase-2-knowledge-memory, Property: Temporal Field Round-Trip
# Feature: phase-2-knowledge-memory, Property: Time-Range Ordering
"""
import pytest
from datetime import datetime, timezone
from hypothesis import given, settings, strategies as st

from services.memory.temporal import TemporalMemoryStore, ISO_FMT


def _make_store(memories, vector=None):
    def _save(_self, new_entries):
        snapshot = list(new_entries)  # may alias `memories`; snapshot before mutating
        memories[:] = snapshot

    mm = type("MM", (), {
        "load_all": lambda self: memories,
        "save": _save,
    })()
    return TemporalMemoryStore(mm, vector), mm


UTC = timezone.utc


# ── Property: valid ISO datetimes round-trip through validation ──────────────

@given(st.datetimes(
    timezones=st.just(UTC),
    min_value=datetime(2020, 1, 1, tzinfo=UTC),
    max_value=datetime(2040, 1, 1, tzinfo=UTC),
))
@settings(max_examples=60)
def test_iso_roundtrip_validation_accepts_valid(dt):
    store, _ = _make_store([])
    store.validate_temporal_fields(dt.strftime(ISO_FMT), None)  # must not raise


@pytest.mark.parametrize("bad", [
    "not-a-date", "2026-01-01", "2026-01-01T10:00:00", "2026-13-01T10:00:00Z", "",
])
def test_validate_rejects_malformed(bad):
    store, _ = _make_store([])
    with pytest.raises(ValueError):
        store.validate_temporal_fields(bad, None)
    with pytest.raises(ValueError):
        store.validate_temporal_fields(None, bad)


# ── set_temporal ─────────────────────────────────────────────────────────────

def test_set_temporal_attaches_fields_and_default_status():
    store, _ = _make_store([])
    entry = store.set_temporal({"id": "1"}, "2026-01-02T03:04:05Z", "2025-01-01T00:00:00Z")
    assert entry["expires_at"] == "2026-01-02T03:04:05Z"
    assert entry["active_from"] == "2025-01-01T00:00:00Z"
    assert entry["status"] == "active"


# ── is_active / filter_active ────────────────────────────────────────────────

def test_is_active_excludes_archived_and_future_dated():
    store, _ = _make_store([])
    future = (datetime.now(UTC).replace(microsecond=0)).strftime(ISO_FMT)
    # Build a datetime guaranteed in the future regardless of clock skew.
    from datetime import timedelta
    future = (datetime.now(UTC) + timedelta(hours=1)).strftime(ISO_FMT)
    assert store.is_active({"status": "archived"}) is False
    assert store.is_active({"active_from": future}) is False
    assert store.is_active({"status": "active", "active_from": None}) is True


# ── Expiry pass ──────────────────────────────────────────────────────────────

def test_expiry_pass_archives_expired_and_syncs_vector():
    from datetime import timedelta
    past = (datetime.now(UTC) - timedelta(hours=2)).strftime(ISO_FMT)
    future = (datetime.now(UTC) + timedelta(hours=2)).strftime(ISO_FMT)
    memories = [
        {"id": "a", "expires_at": past},
        {"id": "b", "expires_at": future},
        {"id": "c", "expires_at": past, "status": "archived"},
        {"id": "d"},  # no expiry
        {"id": "e", "expires_at": "garbage"},
    ]
    vector = type("V", (), {"remove": lambda self, eid: removed.append(eid)})()
    removed = []
    store, mm = _make_store(memories, vector)
    n = store.run_expiry_pass()
    assert n == 1  # only entry "a"
    assert memories[0]["status"] == "archived"
    assert "archived_at" in memories[0]
    assert removed == ["a"]


# ── Time-range retrieval ─────────────────────────────────────────────────────

@given(
    st.lists(
        st.integers(min_value=1_600_000_000, max_value=2_000_000_000),
        min_size=0, max_size=12, unique=True,
    )
)
@settings(max_examples=40)
def test_time_range_returns_only_in_bounds_and_sorted(timestamps):
    entries = [{"id": str(i), "timestamp": ts} for i, ts in enumerate(timestamps)]
    store, _ = _make_store(entries)
    lo = 1_700_000_000
    hi = 1_900_000_000
    out = store.time_range_query(entries, from_dt=_parse_iso_ts(lo), to_dt=_parse_iso_ts(hi))
    expected = sorted([e for e in entries if lo <= e["timestamp"] <= hi], key=lambda e: e["timestamp"])
    assert [e["id"] for e in out] == [e["id"] for e in expected]


def _parse_iso_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).strftime(ISO_FMT)


def test_time_range_from_after_to_returns_empty():
    store, _ = _make_store([{"id": "1", "timestamp": 1_800_000_000}])
    assert store.time_range_query(
        [{"id": "1", "timestamp": 1_800_000_000}],
        from_dt=_parse_iso_ts(1_900_000_000),
        to_dt=_parse_iso_ts(1_700_000_000),
    ) == []


def test_time_range_excludes_archived_unless_requested():
    store, _ = _make_store([])
    entries = [
        {"id": "a", "timestamp": 1_800_000_000, "status": "archived"},
        {"id": "b", "timestamp": 1_800_000_001},
    ]
    out = store.time_range_query(entries, from_dt=_parse_iso_ts(1_700_000_000))
    assert [e["id"] for e in out] == ["b"]
    out2 = store.time_range_query(entries, from_dt=_parse_iso_ts(1_700_000_000), include_archived=True)
    assert len(out2) == 2
