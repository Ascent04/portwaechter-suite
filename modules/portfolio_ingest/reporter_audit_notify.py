from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from urllib import parse, request

from modules.common.utils import append_jsonl, ensure_dir, write_json


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_json(obj: object) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True)
    return _sha256_text(payload)


def render_report_md(snapshot: dict, analysis: dict) -> str:
    lines = [
        f"# PortWächter Report ({snapshot.get('asof') or 'ohne Datum'})",
        "",
        "## Snapshot",
        f"- Base Currency: {snapshot.get('base_currency', 'EUR')}",
        f"- Positionen: {len(snapshot.get('positions', []))}",
        f"- PDF Positionen: {snapshot.get('pdf_positions_count')}",
        f"- PDF Gesamtwert: {snapshot.get('pdf_total_value_eur')}",
        f"- Computed Gesamtwert: {snapshot.get('computed_total_eur')}",
        f"- Validation: {snapshot.get('validation_status')}",
        "",
        "## Analyse",
        f"- Gesamtwert: {analysis.get('total_value_eur')} EUR",
        f"- Core Gesamtwert: {analysis.get('core_total_eur')} EUR",
        f"- Derivate: {analysis.get('derivatives_count')}",
        "",
        "## Top 10 Core",
    ]

    for pos in analysis.get("top10_core", []):
        lines.append(
            f"- {pos.get('name')} ({pos.get('isin')}): "
            f"{pos.get('market_value_eur')} EUR ({pos.get('weight_pct')}%)"
        )

    lines.extend(["", "## Alerts"])
    for alert in analysis.get("alerts", []):
        lines.append(f"- {alert.get('id')}: {alert.get('message')}")

    return "\n".join(lines) + "\n"


def persist_artifacts(run_id: str, snapshot: dict, analysis: dict, report_md: str, root_dir: str) -> dict:
    root = Path(root_dir)
    report_path = root / "data" / "reports" / f"report_{run_id}.md"
    snapshot_path = root / "data" / "snapshots" / f"portfolio_{run_id}.json"
    analysis_path = root / "data" / "snapshots" / f"analysis_{run_id}.json"

    ensure_dir(report_path.parent)
    ensure_dir(snapshot_path.parent)

    report_path.write_text(report_md, encoding="utf-8")
    write_json(snapshot_path, snapshot)
    write_json(analysis_path, analysis)

    return {
        "report_path": str(report_path),
        "snapshot_path": str(snapshot_path),
        "analysis_path": str(analysis_path),
        "snapshot_hash": _sha256_json(snapshot),
        "report_hash": _sha256_text(report_md),
    }


def append_audit_event(event: dict, audit_jsonl_path: str) -> None:
    audit_path = Path(audit_jsonl_path)
    ensure_dir(audit_path.parent)
    append_jsonl(audit_path, event)


def maybe_send_telegram(text: str, cfg: dict) -> None:
    tg_cfg = cfg.get("notify", {}).get("telegram", {})
    if not tg_cfg.get("enabled", False):
        return

    token_env = tg_cfg.get("bot_token_env", "TG_BOT_TOKEN")
    chat_id_env = tg_cfg.get("chat_id_env", "TG_CHAT_ID")
    token = os.getenv(token_env)
    chat_id = os.getenv(chat_id_env)

    if not token or not chat_id:
        return

    payload = parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    req = request.Request(url, data=payload, method="POST")
    try:
        with request.urlopen(req, timeout=10):
            return
    except Exception:
        return
