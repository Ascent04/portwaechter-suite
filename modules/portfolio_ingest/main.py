from __future__ import annotations

import argparse
import uuid
from pathlib import Path

from modules.common.config import load_config
from modules.common.utils import now_iso_tz
from modules.portfolio_ingest.analyzer import analyze
from modules.portfolio_ingest.collector import collect_latest_pdf
from modules.portfolio_ingest.normalizer import normalize_snapshot
from modules.portfolio_ingest.parser_tr_pdf import parse_tr_depotauszug
from modules.portfolio_ingest.reporter_audit_notify import (
    append_audit_event,
    maybe_send_telegram,
    persist_artifacts,
    render_report_md,
)


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _raw_dir(cfg: dict) -> Path:
    root = _root_dir(cfg)
    raw_cfg = cfg.get("paths", {}).get("raw")
    return Path(raw_cfg) if raw_cfg else (root / "data" / "raw")


def _audit_path(cfg: dict) -> Path:
    root = _root_dir(cfg)
    configured = cfg.get("paths", {}).get("audit_jsonl")
    return Path(configured) if configured else (root / "data" / "audit" / "portfolio_audit.jsonl")


def run() -> None:
    cfg = load_config()
    timezone = cfg.get("app", {}).get("timezone", "Europe/Berlin")

    started_at = now_iso_tz(timezone)
    run_id = str(uuid.uuid4())
    status = "failed"
    raw_sha256 = None
    snapshot_hash = None
    report_hash = None
    alert_ids: list[str] = []

    try:
        inbox = cfg["portfolio"]["source"]["inbox"]
        fingerprint = collect_latest_pdf(inbox, _raw_dir(cfg))

        run_id = fingerprint["run_id"]
        raw_sha256 = fingerprint.get("sha256")

        parsed = parse_tr_depotauszug(fingerprint["dst_path"])
        snapshot = normalize_snapshot(
            parsed,
            base_currency=cfg.get("app", {}).get("base_currency", "EUR"),
        )
        snapshot["run_id"] = run_id

        analysis = analyze(snapshot)
        report_md = render_report_md(snapshot, analysis)

        artifacts = persist_artifacts(run_id, snapshot, analysis, report_md, str(_root_dir(cfg)))
        snapshot_hash = artifacts["snapshot_hash"]
        report_hash = artifacts["report_hash"]

        alert_ids = [alert.get("id") for alert in analysis.get("alerts", []) if alert.get("id")]
        status = snapshot.get("validation_status", "ok")

        telegram_text = (
            f"PortWächter Portfolio {status} | "
            f"Wert {analysis.get('total_value_eur')} EUR | "
            f"Alerts: {', '.join(alert_ids) if alert_ids else 'none'}"
        )
        maybe_send_telegram(telegram_text, cfg)
    finally:
        event = {
            "run_id": run_id,
            "started_at": started_at,
            "finished_at": now_iso_tz(timezone),
            "raw_sha256": raw_sha256,
            "snapshot_hash": snapshot_hash,
            "report_hash": report_hash,
            "status": status,
            "alert_ids": alert_ids,
        }
        append_audit_event(event, str(_audit_path(cfg)))


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Portfolio ingest runner")
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()

    if args.command == "run":
        run()


if __name__ == "__main__":
    _cli()
