from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from urllib import parse, request

from modules.common.state import load_state, mark_sent, save_state, should_send
from modules.common.utils import ensure_dir, now_iso_tz, read_json, write_json
from modules.optimizer_engine.heuristics import propose_rebalance
from modules.optimizer_engine.reporter import render_optimizer_md


def _latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern))
    return files[-1] if files else None


def _send_telegram(text: str, cfg: dict) -> bool:
    tg_cfg = cfg.get("notify", {}).get("telegram", {})
    if not tg_cfg.get("enabled", False):
        return False

    token = os.getenv(tg_cfg.get("bot_token_env", "TG_BOT_TOKEN"))
    chat_id = os.getenv(tg_cfg.get("chat_id_env", "TG_CHAT_ID"))
    if not token or not chat_id:
        return False

    payload = parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, method="POST")
    try:
        with request.urlopen(req, timeout=10):
            return True
    except Exception:
        return False


def run(cfg: dict) -> dict:
    if not cfg.get("optimizer", {}).get("enabled", True):
        return {"status": "disabled", "actions": []}

    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    snapshots_dir = root / "data" / "snapshots"

    snapshot_path = _latest(snapshots_dir, "portfolio_*.json")
    analysis_path = _latest(snapshots_dir, "analysis_*.json")
    if not snapshot_path or not analysis_path:
        return {"status": "missing_inputs", "actions": []}

    snapshot = read_json(snapshot_path)
    analysis = read_json(analysis_path)
    proposal = propose_rebalance(snapshot, analysis, cfg)

    run_id = snapshot.get("run_id") or str(uuid.uuid4())
    report_path = root / "data" / "reports" / f"optimizer_{run_id}.md"
    proposal_path = root / "data" / "reports" / f"optimizer_{run_id}.json"

    ensure_dir(report_path.parent)
    report_path.write_text(render_optimizer_md(proposal), encoding="utf-8")
    write_json(proposal_path, proposal)

    state_path = root / "data" / "state" / "notify_state.json"
    state = load_state(state_path)

    digest = hashlib.sha256(
        json.dumps(proposal.get("actions", []), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    key = f"optimizer:{run_id}:{digest}"

    now_iso = now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))
    cooldown = int(cfg.get("notify", {}).get("telegram", {}).get("cooldown_min", 30))

    if should_send(key, now_iso, cooldown, state):
        reduce_count = sum(1 for a in proposal.get("actions", []) if a.get("type") == "reduce")
        text = (
            "PortWächter Optimizer\n"
            f"Actions: {len(proposal.get('actions', []))}\n"
            f"Reduce: {reduce_count}\n"
            f"Report: {report_path.name}"
        )
        if _send_telegram(text, cfg):
            mark_sent(key, now_iso, state)
            save_state(state_path, state)

    return {
        "status": "ok",
        "report_path": str(report_path),
        "proposal_path": str(proposal_path),
        "proposal": proposal,
    }
