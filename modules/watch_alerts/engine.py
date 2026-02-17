from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from modules.common.utils import now_iso_tz, read_json, write_json
from modules.performance.notifier import send_performance_text


def _latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern))
    return files[-1] if files else None


def _read_jsonl(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _state_path(cfg: dict) -> Path:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    return root / "data" / "watch_alerts" / "state.json"


def load_state(cfg: dict) -> dict:
    path = _state_path(cfg)
    if not path.exists():
        return {"day": "", "sent_today_count": 0, "per_isin_last_sent_ts": {}, "dedupe_keys": [], "last_volume_lights": {}, "last_regime": None, "last_regime_sent_day": ""}
    data = read_json(path)
    return data if isinstance(data, dict) else {}


def save_state(cfg: dict, state: dict) -> None:
    write_json(_state_path(cfg), state)


def _parse_iso(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None


def should_send(isin: str, alert_type: str, now: datetime, cfg: dict, state: dict) -> bool:
    wa = cfg.get("watch_alerts", {})
    if not wa.get("enabled", True):
        return False

    day = now.date().isoformat()
    if state.get("day") != day:
        state["day"] = day
        state["sent_today_count"] = 0
        state["dedupe_keys"] = []

    if int(state.get("sent_today_count", 0)) >= int(wa.get("max_per_day", 5)):
        return False

    key = f"WATCH:{alert_type}:{isin}:{day}"
    if key in set(state.get("dedupe_keys", [])):
        return False

    cooldown = int(wa.get("cooldown_minutes_per_isin", 360))
    last_iso = (state.get("per_isin_last_sent_ts") or {}).get(isin)
    last = _parse_iso(last_iso)
    if last and now - last < timedelta(minutes=cooldown):
        return False

    return True


def build_watch_message(candidate: dict) -> str:
    reasons = ", ".join(candidate.get("reasons", [])[:3])
    parts = [
        f"WATCH: {candidate.get('name') or 'n/a'} ({candidate.get('isin')})",
        f"Grund: {reasons or 'Signal/News'}",
    ]
    if candidate.get("score") is not None or candidate.get("confidence"):
        parts.append(f"Score/Confidence: {candidate.get('score', 'n/a')} / {candidate.get('confidence', 'n/a')}")
    parts.append(f"Regime: {candidate.get('regime', 'neutral')}")
    if candidate.get("news_source") or candidate.get("news_title"):
        parts.append(f"News: {candidate.get('news_source', 'n/a')} - {candidate.get('news_title', '')[:120]}")
    parts.append("Beobachten, keine Handlungsempfehlung.")
    return "\n".join(parts)[:1190]


def _load_inputs(cfg: dict) -> tuple[set[str], list[dict], list[dict], dict, str]:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))

    snap_path = _latest(root / "data" / "snapshots", "portfolio_*.json")
    holdings = set()
    if snap_path:
        data = read_json(snap_path)
        holdings = {str(p.get("isin")) for p in data.get("positions", []) if p.get("isin")}

    sig_path = _latest(root / "data" / "signals", "signals_*.jsonl")
    signals = [s for s in _read_jsonl(sig_path) if s.get("id") == "MULTI_FACTOR_SIGNAL"]

    news = []
    top_path = _latest(root / "data" / "news", "top_opportunities_*.json")
    if top_path:
        top = read_json(top_path)
        news.extend(top.get("top", []))
    items_path = _latest(root / "data" / "news", "items_translated_*.jsonl")
    news.extend(_read_jsonl(items_path)[:100])

    briefing_path = _latest(root / "data" / "briefings", "morning_*.json")
    volume_lights, regime = {}, "neutral"
    if briefing_path:
        b = read_json(briefing_path)
        regime = (b.get("regime") or {}).get("regime", "neutral")
        for row in (b.get("volume_lights") or {}).get("holdings", []):
            if row.get("isin"):
                volume_lights[str(row.get("isin"))] = str(row.get("light", "gray"))

    return holdings, signals, news, volume_lights, regime


def run(cfg: dict) -> None:
    try:
        wa = cfg.get("watch_alerts", {})
        if not wa.get("enabled", True):
            return

        holdings, signals, news, volume_lights, regime = _load_inputs(cfg)
        state = load_state(cfg)
        now = datetime.fromisoformat(now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin")))

        candidates = []
        min_score = float(wa.get("min_score", 3))

        if wa.get("include_holdings", True):
            for s in signals:
                isin = str(s.get("isin") or "")
                score = float(s.get("factor_score", 0) or 0)
                if isin in holdings and score >= min_score:
                    candidates.append({"alert_type": "signal", "isin": isin, "name": s.get("name"), "reasons": ["multi_factor"], "score": score, "confidence": "n/a", "regime": regime})

        for n in news:
            isin = str(n.get("isin") or "")
            if not isin:
                continue
            is_holding = isin in holdings
            if (is_holding and not wa.get("include_holdings", True)) or ((not is_holding) and not wa.get("include_radar", True)):
                continue
            candidates.append({"alert_type": "news", "isin": isin, "name": n.get("name") or n.get("title"), "reasons": ["news"], "score": n.get("score"), "confidence": n.get("confidence", "n/a"), "regime": regime, "news_source": n.get("source"), "news_title": n.get("title_de") or n.get("title")})

        prefer = [str(x).lower() for x in wa.get("prefer_sources", [])]
        if prefer:
            def _rank(item: dict) -> int:
                src = str(item.get("news_source", "")).lower()
                for idx, key in enumerate(prefer):
                    if key in src:
                        return idx
                return len(prefer)
            candidates.sort(key=_rank)

        old_lights = state.get("last_volume_lights", {}) if isinstance(state.get("last_volume_lights"), dict) else {}
        for isin, light in volume_lights.items():
            if light == "red" and old_lights.get(isin) != "red":
                candidates.append({"alert_type": "volume_red", "isin": isin, "name": isin, "reasons": ["volume_red"], "score": None, "confidence": "n/a", "regime": regime})

        if state.get("last_regime") and state.get("last_regime") != regime and state.get("last_regime_sent_day") != now.date().isoformat():
            candidates.append({"alert_type": "regime_change", "isin": "GLOBAL", "name": "Regime", "reasons": [f"{state.get('last_regime')}->{regime}"], "score": None, "confidence": "n/a", "regime": regime})

        sent = 0
        for c in candidates:
            isin = str(c.get("isin") or "GLOBAL")
            alert_type = str(c.get("alert_type") or "watch")
            if not should_send(isin, alert_type, now, cfg, state):
                continue
            ok = send_performance_text(build_watch_message(c), cfg)
            if not ok:
                continue
            state["sent_today_count"] = int(state.get("sent_today_count", 0)) + 1
            state.setdefault("per_isin_last_sent_ts", {})[isin] = now.isoformat()
            key = f"WATCH:{alert_type}:{isin}:{now.date().isoformat()}"
            state.setdefault("dedupe_keys", []).append(key)
            sent += 1

        state["last_volume_lights"] = volume_lights
        state["last_regime"] = regime
        if sent and any(c.get("alert_type") == "regime_change" for c in candidates):
            state["last_regime_sent_day"] = now.date().isoformat()
        save_state(cfg, state)
    except Exception:
        return
