from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from modules.common.utils import ensure_dir, now_iso_tz
from modules.performance.notifier import send_performance_text
from modules.v2.config import data_dir, v2_telegram
from modules.v2.telegram.copy import format_score, market_label, normalize_confidence, short_name
from modules.watch_alerts.helpers import now_berlin


def _state_path(cfg: dict) -> Path:
    return data_dir(cfg) / "telegram_state.json"


def _default_state(today: str) -> dict:
    return {"date": today, "counters": {"watch": 0, "action": 0, "defense": 0}, "sent": {}, "dedupe": []}


def _load_state(cfg: dict) -> dict:
    path = _state_path(cfg)
    today = date.today().isoformat()
    if not path.exists():
        return _default_state(today)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_state(today)
    if str(state.get("date")) != today:
        return _default_state(today)
    return state


def _save_state(cfg: dict, state: dict) -> None:
    path = _state_path(cfg)
    ensure_dir(path.parent)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _limit(kind: str, cfg: dict) -> int:
    tcfg = v2_telegram(cfg)
    mapping = {"watch": "watch_max_per_day", "action": "action_max_per_day", "defense": "defense_max_per_day"}
    return int(tcfg.get(mapping[kind], 0) or 0)


def _entity_key(candidate: dict) -> str:
    return str(candidate.get("symbol") or candidate.get("isin") or candidate.get("name") or "na")


def _state_key(kind: str, entity_key: str, now: datetime) -> str:
    return f"{kind}:{entity_key}:{now.date().isoformat()}"


def _should_send(kind: str, key: str, cfg: dict, state: dict, now: datetime) -> bool:
    if key in set(state.get("dedupe", [])):
        return False
    counters = state.setdefault("counters", {})
    if int(counters.get(kind, 0) or 0) >= _limit(kind, cfg):
        return False

    cooldown = timedelta(minutes=int(v2_telegram(cfg).get("cooldown_minutes", 90) or 90))
    raw = state.setdefault("sent", {}).get(key)
    if not raw:
        return True
    try:
        last = datetime.fromisoformat(raw)
    except ValueError:
        return True
    return now - last >= cooldown


def _send(kind: str, entity_key: str, text: str, cfg: dict) -> bool:
    now = now_berlin(cfg.get("app", {}).get("timezone", "Europe/Berlin"))
    key = _state_key(kind, entity_key, now)
    state = _load_state(cfg)
    if not _should_send(kind, key, cfg, state, now):
        return False
    if not send_performance_text(text, cfg):
        return False
    state.setdefault("dedupe", []).append(key)
    state.setdefault("sent", {})[key] = now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))
    state.setdefault("counters", {})[kind] = int(state["counters"].get(kind, 0) or 0) + 1
    _save_state(cfg, state)
    return True


def send_watch(candidate: dict, text: str, cfg: dict) -> bool:
    return _send("watch", _entity_key(candidate), text, cfg)


def send_action(candidate: dict, text: str, cfg: dict) -> bool:
    return _send("action", _entity_key(candidate), text, cfg)


def send_defense(candidate: dict, text: str, cfg: dict) -> bool:
    return _send("defense", _entity_key(candidate), text, cfg)


def render_watch_bundle(candidates: list[dict]) -> str:
    rows = sorted(
        [row for row in candidates if row.get("classification") == "WATCH"],
        key=lambda row: float((row.get("opportunity_score") or {}).get("total_score", 0) or 0),
        reverse=True,
    )[:10]
    if not rows:
        return ""

    labels = {"hoch": "Hoch", "mittel": "Mittel", "spekulativ": "Spekulativ"}
    groups = {key: [] for key in ("hoch", "mittel", "spekulativ")}
    for row in rows:
        confidence = normalize_confidence((row.get("opportunity_score") or {}).get("confidence"))
        groups.setdefault(confidence, []).append(row)

    regime = market_label(next((row.get("regime") for row in rows if row.get("regime")), "neutral"))
    example = rows[0].get("symbol") or rows[0].get("isin") or "BAYN.DE"
    lines = ["HALTEN"]
    for key in ("hoch", "mittel", "spekulativ"):
        subset = groups.get(key, [])
        if not subset:
            continue
        lines.extend(["", f"{labels[key]}:"])
        for row in subset:
            score = format_score((row.get("opportunity_score") or {}).get("total_score"))
            lines.append(f"- {short_name(row)} (Score {score})")

    lines.extend(
        [
            "",
            f"Marktlage: {regime}",
            "",
            "Hinweis:",
            "Halten bedeutet: aktuell keine neue Transaktion priorisieren.",
            "",
            "Nuetzliche Befehle:",
            "/top",
            f"/why {example}",
            "/meaning",
            "/status",
            "/proposals",
        ]
    )
    return "\n".join(lines)[:1800]


def send_watch_bundle(candidates: list[dict], cfg: dict) -> bool:
    text = render_watch_bundle(candidates)
    if not text:
        return False
    rows = sorted(
        [row for row in candidates if row.get("classification") == "WATCH"],
        key=lambda row: float((row.get("opportunity_score") or {}).get("total_score", 0) or 0),
        reverse=True,
    )[:10]
    entity_key = "bundle:" + ",".join(_entity_key(row) for row in rows)
    return _send("watch", entity_key, text, cfg)


def send_status(text: str, cfg: dict) -> bool:
    return send_performance_text(text, cfg)
