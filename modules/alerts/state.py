from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def _default_state(today: str | None = None) -> dict:
    d = today or date.today().isoformat()
    return {
        "date": d,
        "counters": {"watch": 0, "marketdata": 0},
        "watch": {},
        "marketdata": {},
        "meta": {"last_volume_lights": {}, "last_regime": None, "last_regime_sent_day": ""},
    }


def _normalize(state: dict, today: str) -> dict:
    if not isinstance(state, dict):
        state = {}

    out = _default_state(today)
    out["counters"].update(state.get("counters", {}) if isinstance(state.get("counters"), dict) else {})
    out["watch"] = state.get("watch", {}) if isinstance(state.get("watch"), dict) else {}
    out["marketdata"] = state.get("marketdata", {}) if isinstance(state.get("marketdata"), dict) else {}
    if isinstance(state.get("meta"), dict):
        out["meta"].update(state.get("meta", {}))

    if str(state.get("date") or "") != today:
        out["date"] = today
        out["counters"] = {"watch": 0, "marketdata": 0}
        for isin, row in list(out["watch"].items()):
            if not isinstance(row, dict):
                out["watch"][isin] = {"last_sent_ts": None, "dedupe": []}
            else:
                out["watch"][isin] = {"last_sent_ts": row.get("last_sent_ts"), "dedupe": []}
    return out


def load_alert_state(path: str) -> dict:
    p = Path(path)
    today = date.today().isoformat()
    if not p.exists():
        return _default_state(today)
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return _default_state(today)
    return _normalize(data, today)


def save_alert_state(path: str, state: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
    tmp.replace(p)
