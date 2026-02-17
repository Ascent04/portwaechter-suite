from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.common.config import load_config
from modules.common.utils import now_iso_tz


def _load_env_file(path: Path) -> dict[str, str]:
    env_map: dict[str, str] = {}
    if not path.exists() or not os.access(path, os.R_OK):
        return env_map

    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        env_map[key.strip()] = value.strip().strip("'").strip('"')
    return env_map


def _safe_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return []


def _latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern))
    return files[-1] if files else None


def _systemd_state() -> str:
    try:
        out = subprocess.run(
            ["systemctl", "is-failed", "portwaechter-portfolio.service"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except Exception:
        return "failed"

    state = out.stdout.strip()
    if state == "failed":
        try:
            detail = subprocess.run(
                ["systemctl", "status", "portwaechter-portfolio.service", "--no-pager"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            ).stdout.lower()
            if "start-limit-hit" in detail:
                return "start-limit-hit"
        except Exception:
            return "failed"
        return "failed"

    return "ok"


def _has_systemd_environment_file() -> bool:
    for unit in (
        "portwaechter-marketdata.service",
        "portwaechter-news.service",
        "portwaechter-portfolio.service",
    ):
        try:
            out = subprocess.run(
                ["systemctl", "cat", unit],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            ).stdout
        except Exception:
            continue
        if "EnvironmentFile=" in out:
            return True
    return False


def _permissions_diagnostics(root_dir: Path) -> dict[str, Any]:
    data_dir = root_dir / "data"
    checked_paths = [str(data_dir)]
    if not data_dir.exists():
        return {
            "status": "ok",
            "offenders_count": 0,
            "offenders_sample": [],
            "checked_paths": checked_paths,
        }

    uid = os.getuid()
    offenders: list[str] = []
    for path in data_dir.rglob("*"):
        try:
            stat = path.stat()
        except OSError:
            continue
        if path.is_file() and stat.st_uid != uid:
            offenders.append(str(path))
            if len(offenders) >= 20:
                break

    return {
        "status": "ok" if not offenders else "root_owned_files",
        "offenders_count": len(offenders),
        "offenders_sample": offenders,
        "checked_paths": checked_paths,
    }


def _portfolio_state(root_dir: Path) -> str:
    snapshots_dir = root_dir / "data" / "snapshots"
    inbox_dir = root_dir / "data" / "inbox"

    has_snapshot = bool(list(snapshots_dir.glob("portfolio_*.json")))
    if has_snapshot:
        return "ok"

    has_pdf = bool(list(inbox_dir.glob("*.pdf")))
    return "fail" if has_pdf else "skipped_no_pdf"


def _marketdata_state(root_dir: Path) -> str:
    market_dir = root_dir / "data" / "marketdata"
    quotes = _latest(market_dir, "quotes_*.jsonl")
    if not quotes:
        return "missing_mapping_only"

    lines = _safe_lines(quotes)
    if not lines:
        return "missing_mapping_only"

    ok_seen = False
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("status") == "ok":
            ok_seen = True
            break

    return "ok" if ok_seen else "missing_mapping_only"


def _news_state(root_dir: Path, cfg: dict[str, Any]) -> str:
    news_dir = root_dir / "data" / "news"
    feeds = cfg.get("news", {}).get("feed_sources", [])

    items = _latest(news_dir, "items_*.jsonl")
    ranked = _latest(news_dir, "top_opportunities_*.json")
    translated = _latest(news_dir, "items_translated_*.jsonl")

    if not items and not ranked and not translated:
        return "no_feeds" if not feeds else "parse_fail"

    if ranked and ranked.exists():
        return "ok"
    if items and items.exists():
        return "ok"
    if translated and translated.exists():
        return "ok"
    return "parse_fail"


def _signals_state(root_dir: Path) -> str:
    signals_dir = root_dir / "data" / "signals"
    latest = _latest(signals_dir, "signals_*.jsonl")
    if not latest:
        return "input_missing"

    return "ok" if _safe_lines(latest) else "0_signals"


def _telegram_state(cfg: dict[str, Any]) -> str:
    tg_cfg = cfg.get("notify", {}).get("telegram", {})
    if not tg_cfg.get("enabled", False):
        return "missing_env"

    token_env = tg_cfg.get("bot_token_env", "TG_BOT_TOKEN")
    chat_id_env = tg_cfg.get("chat_id_env", "TG_CHAT_ID")
    token = os.getenv(token_env)
    chat = os.getenv(chat_id_env)
    if token and chat:
        return "ok"

    env_file = Path(tg_cfg.get("env_file", "/etc/portwaechter/portwaechter.env"))
    file_env = _load_env_file(env_file)
    token = file_env.get(token_env)
    chat = file_env.get(chat_id_env)
    if token and chat:
        return "ok"

    return "ok" if _has_systemd_environment_file() else "missing_env"


def _allowed(component: str, status: str) -> bool:
    allowed = {
        "portfolio_ingest": {"ok", "skipped_no_pdf"},
        "marketdata": {"ok", "missing_mapping_only"},
        "news": {"ok", "no_feeds"},
        "signals": {"ok", "0_signals", "input_missing"},
        "telegram": {"ok", "cooldown", "missing_env"},
        "systemd": {"ok"},
        "permissions": {"ok"},
    }
    return status in allowed.get(component, {"ok"})


def collect_health_report(cfg: dict[str, Any] | None = None, root_dir: str | Path | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    root = Path(root_dir) if root_dir else Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    permissions = _permissions_diagnostics(root)

    checks = {
        "portfolio_ingest": _portfolio_state(root),
        "marketdata": _marketdata_state(root),
        "news": _news_state(root, cfg),
        "signals": _signals_state(root),
        "telegram": _telegram_state(cfg),
        "systemd": _systemd_state(),
        "permissions": permissions["status"],
    }

    overall_ok = all(_allowed(component, status) for component, status in checks.items())
    return {
        "generated_at": now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin")),
        "head": datetime.now().isoformat(),
        "checks": checks,
        "details": {
            "permissions": {
                "offenders_count": permissions["offenders_count"],
                "offenders_sample": permissions["offenders_sample"],
                "checked_paths": permissions["checked_paths"],
            }
        },
        "overall_status": "ok" if overall_ok else "failed",
    }


def _cli() -> None:
    parser = argparse.ArgumentParser(description="PortWächter health report")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    report = collect_health_report()
    if args.pretty:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    _cli()
