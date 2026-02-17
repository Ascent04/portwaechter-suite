from __future__ import annotations

from datetime import datetime, timedelta


def _extract_return_pct(item: dict) -> float | None:
    if "r_pct" in item and item.get("r_pct") is not None:
        try:
            return float(item.get("r_pct"))
        except (TypeError, ValueError):
            return None

    horizons = item.get("horizons") if isinstance(item.get("horizons"), dict) else {}
    for key in ("1d", "3d", "5d"):
        h = horizons.get(key) if isinstance(horizons.get(key), dict) else {}
        if h.get("status") == "ok" and h.get("r_pct") is not None:
            try:
                return float(h.get("r_pct"))
            except (TypeError, ValueError):
                return None
    return None


def compute_equity_curve(outcomes: list[dict]) -> list[float]:
    equity = 1.0
    curve = [equity]
    for item in outcomes:
        r = _extract_return_pct(item)
        if r is None:
            continue
        equity *= 1 + (r / 100.0)
        if equity < 0:
            equity = 0.0
        curve.append(equity)
    return curve


def compute_max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0

    peak = max(float(equity_curve[0]), 0.0)
    max_dd = 0.0
    for value in equity_curve:
        v = max(float(value), 0.0)
        if v > peak:
            peak = v
        if peak <= 0:
            continue
        dd = ((peak - v) / peak) * 100.0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 4)


def compute_rolling_drawdown(outcomes: list[dict], window_days: int = 30) -> list[dict]:
    if not outcomes:
        return []

    rows = []
    parsed = []
    for item in outcomes:
        ts = str(item.get("ts_eval") or item.get("ts") or "")
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            continue
        parsed.append((dt, item))
    parsed.sort(key=lambda x: x[0])

    for asof, _ in parsed:
        start = asof - timedelta(days=max(1, int(window_days)))
        window = [item for dt, item in parsed if start <= dt <= asof]
        curve = compute_equity_curve(window)
        rows.append({"asof": asof.date().isoformat(), "max_drawdown_pct": compute_max_drawdown(curve)})
    return rows
