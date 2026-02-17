from __future__ import annotations

from pathlib import Path

from modules.common.state import load_state, mark_sent, save_state, should_send
from modules.common.utils import now_iso_tz, read_json
from modules.performance.notifier import send_performance_text


def build_kpi_dashboard(snapshot: dict) -> str:
    k = snapshot.get("kpis", {}) if isinstance(snapshot, dict) else {}
    s = snapshot.get("status", {}) if isinstance(snapshot, dict) else {}

    lines = [
        "📈 TACTICAL VALIDATION",
        "",
        f"n_total: {int(k.get('n_total', 0) or 0)}",
        f"3d Exp: {float(k.get('exp_3d', 0) or 0):+.2f}%",
        f"Score≥3: {float(k.get('score3_exp_3d', 0) or 0):+.2f}%",
        f"risk_on: {float(k.get('risk_on_exp_3d', 0) or 0):+.2f}%",
        f"Drawdown: {float(k.get('max_tactical_drawdown_pct', 0) or 0):.1f}%",
        "",
        "Status:",
        f"{'✔' if bool(s.get('exp_positive')) else '✖'} Exp stabil",
        f"{'✔' if bool(s.get('score_gradient_ok')) else '✖'} Score Gradient",
        f"{'✔' if bool(s.get('regime_effect_ok')) else '✖'} Regime Edge",
        f"{'✔' if bool(s.get('drawdown_ok')) else '✖'} Drawdown OK",
    ]
    return "\n".join(lines)[:1490]


def _count_weeks(cfg: dict) -> int:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    count = 0
    for path in (root / "data" / "validation").glob("snapshots_*.json"):
        try:
            data = read_json(path)
        except Exception:
            continue
        if isinstance(data, dict) and isinstance(data.get("items"), list) and data["items"]:
            count += 1
        elif isinstance(data, list) and data:
            count += 1
    return count


def send_dashboard_if_enabled(snapshot: dict, cfg: dict) -> None:
    try:
        if not cfg.get("validation", {}).get("telegram_enabled", True):
            print("validation_dashboard_disabled")
            return

        if _count_weeks(cfg) < 4:
            print("validation_dashboard_skipped_lt4weeks")
            return

        week = str(snapshot.get("week") or "unknown")
        root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
        state_path = root / "data" / "state" / "notify_state.json"
        state = load_state(state_path)
        key = f"VALIDATION_DASHBOARD:{week}"
        now_iso = now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin"))

        if not should_send(key, now_iso, 7 * 24 * 60, state):
            print("validation_dashboard_skipped_already_sent")
            return

        sent = send_performance_text(build_kpi_dashboard(snapshot), cfg)
        if sent:
            mark_sent(key, now_iso, state)
            save_state(state_path, state)
            print("validation_dashboard_sent")
        else:
            print("validation_dashboard_send_failed")
    except Exception as exc:
        print(f"validation_dashboard_error:{type(exc).__name__}")
