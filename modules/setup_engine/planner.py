from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib import parse, request
from uuid import uuid4

from modules.common.state import load_state, mark_sent, save_state, should_send
from modules.common.utils import append_jsonl, now_iso_tz, read_json, write_json
from modules.performance.log_events import append_event, build_setup_event


def _latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern))
    return files[-1] if files else None


def _to_float(value: object, default: float | None = None) -> float | None:
    try:
        if value in (None, "", "unknown"):
            return default
        if isinstance(value, str) and value.startswith("{{"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def risk_budget(cfg: dict, portfolio_value: float | None = None) -> dict:
    settings = cfg.get("decision", {})
    risk_pct = _to_float(settings.get("max_risk_per_trade_pct"), 0.75) or 0.75
    pval = portfolio_value if portfolio_value is not None else _to_float(settings.get("portfolio_value_eur"), None)
    return {"risk_pct": risk_pct, "portfolio_value_eur": pval, "risk_eur": (pval * risk_pct / 100.0) if pval else None}


def build_setup(candidate: dict, marketdata: dict, cfg: dict) -> dict:
    close = _to_float(marketdata.get("close"), None)
    direction = "up" if str(candidate.get("direction", "up")).lower() in {"bullish", "up"} else "down"
    budget = risk_budget(cfg)

    if close is None:
        entry = "manual_required"
        stop = "manual_required"
        qty = "manual_required"
        invalidation = "ANNAHME: manual_required"
    else:
        entry_low = round(close * 0.995, 4)
        entry_high = round(close * 1.005, 4)
        entry = [entry_low, entry_high]
        stop_val = round(close * (0.97 if direction == "up" else 1.03), 4)
        stop = stop_val
        dist = abs(close - stop_val)
        qty = int((budget["risk_eur"] / dist)) if budget.get("risk_eur") and dist > 0 else "manual_required"
        invalidation = f"Close {'<' if direction == 'up' else '>'} {stop_val}"

    return {
        "setup_id": f"setup-{uuid4()}",
        "created_at": now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin")),
        "candidate": {
            "isin": candidate.get("isin"),
            "name": candidate.get("name"),
            "direction": direction,
            "score": candidate.get("score"),
            "bucket": candidate.get("bucket"),
            "confidence": candidate.get("confidence"),
        },
        "entry_zone": entry,
        "stop": stop,
        "invalidation": invalidation,
        "risk_budget": budget,
        "position_size": qty,
        "checklist": [
            "News geprüft",
            "Liquidität ok",
            "Spreads ok",
            "Terminrisiko geprüft",
            "Kein Auto-Trade",
        ],
        "status": "pending_approval",
    }


def render_setup_text(setup_json: dict) -> str:
    c = setup_json.get("candidate", {})
    lines = [
        f"Setup Prep {c.get('name') or c.get('isin')}",
        f"ID: {setup_json.get('setup_id')}",
        f"Score: {c.get('score')} | Direction: {c.get('direction')}",
        f"Entry: {setup_json.get('entry_zone')}",
        f"Stop/Invalidation: {setup_json.get('stop')} / {setup_json.get('invalidation')}",
        f"RiskBudget: {setup_json.get('risk_budget')}",
        f"Size: {setup_json.get('position_size')}",
        "Status: Monitoring (keine Ausführung)",
        "APPROVE SETUP <id> | REJECT SETUP <id>",
    ]
    return "\n".join(lines)[:3400]


def enqueue_setup_for_approval(setup_json: dict, cfg: dict) -> Path:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    out_dir = root / "data" / "setups"
    out_dir.mkdir(parents=True, exist_ok=True)
    setup_file = out_dir / f"{setup_json['setup_id']}.json"
    write_json(setup_file, setup_json)
    append_jsonl(out_dir / f"pending_{datetime.now().strftime('%Y%m%d')}.jsonl", setup_json)
    if cfg.get("performance", {}).get("enabled", True):
        try:
            append_event(build_setup_event(setup_json, cfg), cfg)
        except Exception:
            pass
    return setup_file


def handle_approval_command(msg: str, cfg: dict) -> dict:
    match = re.search(r"^(APPROVE|REJECT)\s+SETUP\s+([A-Za-z0-9\-]+)$", msg.strip(), flags=re.IGNORECASE)
    if not match:
        return {"status": "ignored", "reason": "invalid_command"}

    action = match.group(1).lower()
    setup_id = match.group(2)
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    setup_file = root / "data" / "setups" / f"{setup_id}.json"
    if not setup_file.exists():
        return {"status": "not_found", "setup_id": setup_id}

    setup = read_json(setup_file)
    setup["status"] = "approved" if action == "approve" else "rejected"
    setup["decision_at"] = now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))
    write_json(setup_file, setup)
    append_jsonl(root / "data" / "setups" / "approvals.jsonl", {"setup_id": setup_id, "action": action, "at": setup["decision_at"]})
    return {"status": setup["status"], "setup_id": setup_id}


def _send_telegram(text: str, cfg: dict) -> bool:
    tg = cfg.get("notify", {}).get("telegram", {})
    if not tg.get("enabled", False):
        return False
    token = os.getenv(tg.get("bot_token_env", "TG_BOT_TOKEN"))
    chat_id = os.getenv(tg.get("chat_id_env", "TG_CHAT_ID"))
    if not token or not chat_id:
        return False
    payload = parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, method="POST")
    try:
        with request.urlopen(req, timeout=10):
            return True
    except Exception:
        return False


def notify_setup(setup_json: dict, cfg: dict) -> None:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    state_path = root / "data" / "state" / "notify_state.json"
    state = load_state(state_path)
    now_iso = now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))
    cooldown = int(cfg.get("notify", {}).get("telegram", {}).get("cooldown_min", 30))
    key = f"SETUP:{setup_json.get('candidate', {}).get('isin')}"
    if not should_send(key, now_iso, cooldown, state):
        return
    if _send_telegram(render_setup_text(setup_json), cfg):
        mark_sent(key, now_iso, state)
        save_state(state_path, state)
