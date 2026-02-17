from __future__ import annotations

from datetime import date

from modules.performance.collect_events import load_events
from modules.performance.log_events import append_event
from modules.performance.outcomes import append_outcome, dedupe_outcomes


def test_append_event_and_load_events(tmp_path) -> None:
    cfg = {"app": {"root_dir": str(tmp_path)}}
    append_event({"ts": "2026-02-17T10:00:00+01:00", "event_type": "signal", "signal_id": "X"}, cfg)
    rows = load_events(date(2026, 2, 17), date(2026, 2, 17), cfg)
    assert len(rows) == 1
    assert rows[0]["signal_id"] == "X"


def test_load_events_tolerant_missing_files(tmp_path) -> None:
    cfg = {"app": {"root_dir": str(tmp_path)}}
    rows = load_events(date(2026, 2, 1), date(2026, 2, 3), cfg)
    assert rows == []


def test_outcomes_dedupe(tmp_path) -> None:
    cfg = {"app": {"root_dir": str(tmp_path)}}
    outcome = {"ts_eval": "2026-02-24T08:00:00+01:00", "signal_id": "SIG-1", "event_type": "signal", "horizons": {}}
    append_outcome(outcome, cfg)
    assert dedupe_outcomes("SIG-1", "2026-02-24", cfg) is True
    assert dedupe_outcomes("SIG-2", "2026-02-24", cfg) is False
