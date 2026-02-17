from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from modules.common.config import load_config
from modules.common.utils import now_iso_tz, read_json, write_json
from modules.validation.telegram_dashboard import send_dashboard_if_enabled


def _week_tag(dt: datetime | None = None) -> str:
    d = dt or datetime.now()
    iso = d.isocalendar()
    return f"{iso.year}W{iso.week:02d}"


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_drawdown(report: dict) -> float:
    direct = _safe_float(report.get("max_tactical_drawdown_pct"), -1.0)
    if direct >= 0:
        return direct
    risk = report.get("risk") if isinstance(report.get("risk"), dict) else {}
    risk_dd = _safe_float((risk or {}).get("max_tactical_drawdown_pct"), -1.0)
    if risk_dd >= 0:
        return risk_dd
    by_h = report.get("by_horizon") if isinstance(report.get("by_horizon"), dict) else {}
    return _safe_float((by_h.get("3d") or {}).get("avg_loss"), 0.0)


def build_weekly_validation_snapshot(report: dict, cfg: dict) -> dict:
    by_h = report.get("by_horizon") if isinstance(report.get("by_horizon"), dict) else {}
    by_reg = report.get("by_regime") if isinstance(report.get("by_regime"), dict) else {}
    by_bucket = report.get("by_bucket") if isinstance(report.get("by_bucket"), dict) else {}

    n_total = int((report.get("summary") or {}).get("events_total", 0))
    exp_3d = _safe_float((by_h.get("3d") or {}).get("expectancy"), 0.0)
    score3_exp = _safe_float((by_bucket.get("factor_score>=3") or {}).get("expectancy"), 0.0)
    risk_on_exp = _safe_float(((by_reg.get("risk_on") or {}).get("3d") or {}).get("expectancy"), 0.0)
    neutral_exp = _safe_float(((by_reg.get("neutral") or {}).get("3d") or {}).get("expectancy"), 0.0)
    drawdown = _extract_drawdown(report)

    dd_limit = _safe_float((cfg.get("validation") or {}).get("monitor") or {}, 5.0)
    if isinstance((cfg.get("validation") or {}).get("monitor"), dict):
        dd_limit = _safe_float((cfg.get("validation") or {}).get("monitor", {}).get("max_tactical_drawdown_pct"), 5.0)

    status = {
        "exp_positive": exp_3d > 0,
        "score_gradient_ok": score3_exp >= exp_3d,
        "regime_effect_ok": risk_on_exp >= neutral_exp,
        "drawdown_ok": drawdown <= dd_limit,
    }

    return {
        "generated_at": now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin")),
        "week": str(report.get("week") or _week_tag()),
        "kpis": {
            "n_total": n_total,
            "exp_3d": exp_3d,
            "score3_exp_3d": score3_exp,
            "risk_on_exp_3d": risk_on_exp,
            "neutral_exp_3d": neutral_exp,
            "max_tactical_drawdown_pct": drawdown,
        },
        "status": status,
    }


def write_snapshot(snapshot: dict, cfg: dict) -> Path:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    week = str(snapshot.get("week", _week_tag())).replace("-", "")
    path = root / "data" / "validation" / f"snapshots_{week}.json"

    items = []
    if path.exists():
        existing = read_json(path)
        if isinstance(existing, list):
            items = existing
        elif isinstance(existing, dict) and isinstance(existing.get("items"), list):
            items = existing.get("items", [])

    items.append(snapshot)
    write_json(path, {"items": items})
    return path


def _load_recent_snapshots(cfg: dict, weeks: int = 12) -> list[dict]:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    files = sorted((root / "data" / "validation").glob("snapshots_*.json"))[-weeks:]
    out = []
    for path in files:
        try:
            data = read_json(path)
        except Exception:
            continue
        if isinstance(data, dict) and isinstance(data.get("items"), list) and data["items"]:
            out.append(data["items"][-1])
        elif isinstance(data, list) and data:
            out.append(data[-1])
    return out


def evaluate_90_day_status(cfg: dict) -> dict:
    snaps = _load_recent_snapshots(cfg, weeks=12)
    if not snaps:
        return {"phase_complete": False, "recommendation": "hold"}

    n_total = sum(int((s.get("kpis") or {}).get("n_total", 0)) for s in snaps)
    exp_vals = [_safe_float((s.get("kpis") or {}).get("exp_3d"), 0.0) for s in snaps]
    score_vals = [_safe_float((s.get("kpis") or {}).get("score3_exp_3d"), 0.0) for s in snaps]
    risk_on_vals = [_safe_float((s.get("kpis") or {}).get("risk_on_exp_3d"), 0.0) for s in snaps]
    neutral_vals = [_safe_float((s.get("kpis") or {}).get("neutral_exp_3d"), 0.0) for s in snaps]

    exp_avg = sum(exp_vals) / len(exp_vals) if exp_vals else 0.0
    score_avg = sum(score_vals) / len(score_vals) if score_vals else 0.0
    risk_on_avg = sum(risk_on_vals) / len(risk_on_vals) if risk_on_vals else 0.0
    neutral_avg = sum(neutral_vals) / len(neutral_vals) if neutral_vals else 0.0

    ok_n = n_total >= 120
    ok_exp = exp_avg >= 0.25
    ok_score = score_avg >= exp_avg
    ok_regime = risk_on_avg >= neutral_avg

    phase_complete = ok_n and ok_exp and ok_score and ok_regime
    if phase_complete:
        recommendation = "scale"
    elif not ok_exp:
        recommendation = "reduce"
    else:
        recommendation = "hold"

    return {
        "phase_complete": phase_complete,
        "recommendation": recommendation,
        "checks": {"n>=120": ok_n, "exp_3d>=0.25": ok_exp, "score3_exp>=exp_total": ok_score, "risk_on_exp>=neutral_exp": ok_regime},
    }


def _latest_weekly_report(cfg: dict) -> dict | None:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    files = sorted((root / "data" / "performance" / "reports").glob("weekly_*.json"))
    if not files:
        return None
    try:
        data = read_json(files[-1])
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def run() -> dict:
    cfg = load_config()
    report = _latest_weekly_report(cfg)
    if not report:
        status = evaluate_90_day_status(cfg)
        print("no_weekly_report")
        return {"snapshot_path": None, "status": status}

    snap = build_weekly_validation_snapshot(report, cfg)
    path = write_snapshot(snap, cfg)
    send_dashboard_if_enabled(snap, cfg)
    status = evaluate_90_day_status(cfg)
    print(f"validation_snapshot={path}")
    return {"snapshot_path": str(path), "status": status}


def _cli() -> None:
    parser = argparse.ArgumentParser(description="90-day validation monitor")
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()
    if args.command == "run":
        run()


if __name__ == "__main__":
    _cli()
