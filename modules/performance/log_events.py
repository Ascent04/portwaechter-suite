from __future__ import annotations

from datetime import datetime
from pathlib import Path

from modules.common.utils import append_jsonl, ensure_dir, now_iso_tz, read_json


def _events_path(cfg: dict, when: datetime | None = None) -> Path:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    dt = when or datetime.now()
    return root / "data" / "performance" / f"events_{dt.strftime('%Y%m%d')}.jsonl"


def _latest_briefing_fields(cfg: dict, isin: str) -> tuple[str, dict]:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    files = sorted((root / "data" / "briefings").glob("morning_*.json"))
    if not files:
        return "neutral", {"light": "gray", "ratio": None, "reason": "unavailable"}

    data = read_json(files[-1])
    regime = (data.get("regime") or {}).get("regime", "neutral")
    for row in (data.get("volume_lights") or {}).get("holdings", []):
        if str(row.get("isin")) == str(isin):
            return regime, {"light": row.get("light", "gray"), "ratio": row.get("ratio"), "reason": row.get("reason", "unavailable")}
    return regime, {"light": "gray", "ratio": None, "reason": "unavailable"}


def build_signal_event(signal: dict, cfg: dict) -> dict:
    direction_raw = str(signal.get("direction", "neutral")).lower()
    direction = "up" if direction_raw in {"bullish", "up"} else "down" if direction_raw in {"bearish", "down"} else "up"
    key = str(signal.get("key", ""))
    ts_part = key.split(":", 3)[-1] if ":" in key else datetime.now().strftime("%H:%M")
    regime, volume = _latest_briefing_fields(cfg, str(signal.get("isin") or ""))
    return {
        "ts": now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin")),
        "event_type": "signal",
        "signal_id": f"MULTI:{signal.get('isin')}:{direction}:{ts_part}",
        "isin": signal.get("isin"),
        "name": signal.get("name"),
        "direction": direction,
        "factor_score": int(signal.get("factor_score", 0)),
        "factors": signal.get("factors", {}),
        "reasons": signal.get("reasons", []),
        "regime": regime,
        "volume_light": volume,
        "source": {"module": "signals_engine", "mode": int(cfg.get("app", {}).get("mode", 2))},
    }


def build_setup_event(setup: dict, cfg: dict) -> dict:
    cand = setup.get("candidate", {})
    direction = str(cand.get("direction", "up"))
    ts = now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))
    return {
        "ts": ts,
        "event_type": "setup",
        "setup_id": f"SETUP:{cand.get('isin')}:{direction}:{ts[:16]}",
        "isin": cand.get("isin"),
        "direction": direction,
        "opportunity_score": cand.get("score"),
        "confidence": cand.get("confidence", "spekulativ"),
        "source": {"module": "setup_engine", "mode": int(cfg.get("app", {}).get("mode", 2))},
    }


def append_event(event: dict, cfg: dict) -> Path:
    path = _events_path(cfg)
    ensure_dir(path.parent)
    append_jsonl(path, event)
    return path
