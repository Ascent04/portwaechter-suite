from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median

from modules.common.utils import now_iso_tz, write_json


HORIZONS = ("1d", "3d", "5d")


def _collect(values: list[dict], horizon: str) -> list[float]:
    out = []
    for row in values:
        h = (row.get("horizons") or {}).get(horizon, {})
        if h.get("status") == "ok" and h.get("r_pct") is not None:
            out.append(float(h.get("r_pct")))
    return out


def _confidence(kpi: dict, min_n: int, min_win_rate_high: float) -> str:
    n = int(kpi.get("n", 0))
    expectancy = float(kpi.get("expectancy", 0.0))
    win_rate = float(kpi.get("win_rate", 0.0))
    if n < min_n:
        return "low"
    if expectancy > 0 and win_rate >= min_win_rate_high:
        return "high"
    if expectancy > 0:
        return "medium"
    return "low"


def _kpis(values: list[float], min_n: int, min_win_rate_high: float) -> dict:
    if not values:
        return {
            "n": 0,
            "win_rate": 0.0,
            "loss_rate": 0.0,
            "avg_r_pct": 0.0,
            "median_r_pct": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "expectancy": 0.0,
            "is_reliable": False,
            "expectancy_confidence": "low",
        }

    wins = [x for x in values if x > 0]
    losses = [x for x in values if x < 0]
    win_rate = len(wins) / len(values)
    loss_rate = len(losses) / len(values)
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss_abs = (abs(sum(losses) / len(losses))) if losses else 0.0
    expectancy = (win_rate * avg_win) - (loss_rate * avg_loss_abs)

    out = {
        "n": len(values),
        "win_rate": round(win_rate, 4),
        "loss_rate": round(loss_rate, 4),
        "avg_r_pct": round(sum(values) / len(values), 4),
        "median_r_pct": round(float(median(values)), 4),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss_abs, 4),
        "expectancy": round(expectancy, 4),
        "is_reliable": len(values) >= min_n,
    }
    out["expectancy_confidence"] = _confidence(out, min_n, min_win_rate_high)
    return out


def _min_n_horizon(cfg: dict, horizon: str) -> int:
    return int(cfg.get("performance", {}).get("min_samples_per_horizon", {}).get(horizon, 20))


def _min_n_bucket(cfg: dict) -> int:
    return int(cfg.get("performance", {}).get("min_samples_per_bucket", 20))


def _wr_high(cfg: dict) -> float:
    return float(cfg.get("performance", {}).get("confidence_rules", {}).get("min_win_rate_high", 0.55))


def _by_horizon(rows: list[dict], cfg: dict) -> dict:
    wr_high = _wr_high(cfg)
    return {h: _kpis(_collect(rows, h), _min_n_horizon(cfg, h), wr_high) for h in HORIZONS}


def _score_calibration(rows: list[dict], cfg: dict) -> dict:
    out = {}
    mins = cfg.get("performance", {}).get("buckets", {}).get("factor_score_min", [2, 3, 4])
    for m in mins:
        subset = [o for o in rows if float(o.get("factor_score", 0)) >= float(m)]
        out[f"factor_score>={m}"] = _by_horizon(subset, cfg)
    return out


def _by_regime(rows: list[dict], cfg: dict) -> dict:
    out = {}
    regimes = cfg.get("performance", {}).get("buckets", {}).get("regimes", ["risk_on", "neutral", "risk_off"])
    for reg in regimes:
        subset = [o for o in rows if o.get("regime") == reg]
        out[reg] = _by_horizon(subset, cfg)
    return out


def _buckets(rows: list[dict], cfg: dict) -> dict:
    out = {}
    wr_high = _wr_high(cfg)
    min_n = _min_n_bucket(cfg)
    for light in cfg.get("performance", {}).get("buckets", {}).get("volume_lights", ["green", "yellow", "red", "gray"]):
        subset = [o for o in rows if ((o.get("volume_light") or {}).get("light") == light)]
        out[f"volume_light={light}"] = _kpis(_collect(subset, "3d"), min_n, wr_high)
    for conf in ("hoch", "mittel", "spekulativ"):
        subset = [o for o in rows if o.get("confidence") == conf]
        out[f"confidence={conf}"] = _kpis(_collect(subset, "3d"), min_n, wr_high)
    for m in cfg.get("performance", {}).get("buckets", {}).get("factor_score_min", [2, 3, 4]):
        subset = [o for o in rows if float(o.get("factor_score", 0)) >= float(m)]
        out[f"factor_score>={m}"] = _kpis(_collect(subset, "3d"), min_n, wr_high)
    for reg in cfg.get("performance", {}).get("buckets", {}).get("regimes", ["risk_on", "neutral", "risk_off"]):
        subset = [o for o in rows if o.get("regime") == reg]
        out[f"regime={reg}"] = _kpis(_collect(subset, "3d"), min_n, wr_high)
    return out


def build_weekly_report(outcomes: list[dict], cfg: dict) -> dict:
    now = datetime.now()
    week = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"

    signals = [o for o in outcomes if o.get("event_type") == "signal"]
    setups = [o for o in outcomes if o.get("event_type") == "setup"]

    by_h = _by_horizon(outcomes, cfg)
    by_regime = _by_regime(outcomes, cfg)
    score_cal = _score_calibration(outcomes, cfg)
    buckets = _buckets(outcomes, cfg)

    per_isin = defaultdict(list)
    for row in outcomes:
        v = (row.get("horizons") or {}).get("3d", {})
        if v.get("status") == "ok" and v.get("r_pct") is not None:
            per_isin[str(row.get("isin"))].append(float(v.get("r_pct")))
    ranking = [{"isin": k, "avg_3d": round(sum(v) / len(v), 4), "n": len(v)} for k, v in per_isin.items() if v]
    ranking.sort(key=lambda x: x["avg_3d"], reverse=True)

    notes = []
    if by_h["3d"]["n"] < _min_n_horizon(cfg, "3d"):
        notes.append("low_sample_size_3d")

    return {
        "generated_at": now_iso_tz(cfg.get("app", {}).get("timezone", "Europe/Berlin")),
        "week": week,
        "summary": {"events_total": len(outcomes), "signals_total": len(signals), "setups_total": len(setups)},
        "by_horizon": by_h,
        "by_regime": by_regime,
        "score_calibration": score_cal,
        "by_bucket": buckets,
        "top_best": ranking[:5],
        "top_worst": list(reversed(ranking[-5:])),
        "notes": notes,
    }


def write_weekly_report(report: dict, cfg: dict) -> Path:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    out_dir = root / "data" / "performance" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"weekly_{report.get('week', 'unknown').replace('-', '')}.json"
    write_json(out, report)
    return out
