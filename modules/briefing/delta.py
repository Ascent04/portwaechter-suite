from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from modules.common.utils import read_json


def find_previous_briefing(path: str | Path, lookback_days: int) -> str | None:
    base = Path(path)
    if not base.exists():
        return None

    today = datetime.now().strftime("%Y%m%d")
    cutoff = datetime.now() - timedelta(days=max(1, lookback_days))
    candidates: list[Path] = []

    for file in base.glob("morning_*.json"):
        stem = file.stem.replace("morning_", "")
        if stem == today:
            continue
        try:
            dt = datetime.strptime(stem, "%Y%m%d")
        except ValueError:
            continue
        if dt >= cutoff:
            candidates.append(file)

    if not candidates:
        return None
    return str(sorted(candidates)[-1])


def load_previous_briefing(file: str | None) -> dict | None:
    if not file:
        return None
    path = Path(file)
    if not path.exists():
        return None
    try:
        data = read_json(path)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def compute_delta(prev: dict | None, curr: dict) -> dict:
    if not prev:
        return {
            "status": "no_previous_briefing",
            "positions_delta": {"top_movers": [], "new_positions": [], "removed_positions": []},
            "radar_delta": {"new_opportunities": [], "dropped_opportunities": []},
        }

    prev_positions = {str(p.get("isin")): p for p in prev.get("positions", []) if p.get("isin")}
    curr_positions = {str(p.get("isin")): p for p in curr.get("positions", []) if p.get("isin")}

    new_positions = sorted([isin for isin in curr_positions if isin not in prev_positions])
    removed_positions = sorted([isin for isin in prev_positions if isin not in curr_positions])

    movers = []
    for isin, now_pos in curr_positions.items():
        old = prev_positions.get(isin)
        if not old:
            continue
        old_pct = float(old.get("pnl_pct") or 0)
        new_pct = float(now_pos.get("pnl_pct") or 0)
        delta_pct = round(new_pct - old_pct, 2)
        movers.append({"isin": isin, "name": now_pos.get("name"), "delta_pnl_pct": delta_pct})
    movers.sort(key=lambda r: abs(r.get("delta_pnl_pct", 0)), reverse=True)

    prev_opp = {str(x.get("isin") or x.get("name")): x for x in prev.get("top_opportunities", [])}
    curr_opp = {str(x.get("isin") or x.get("name")): x for x in curr.get("top_opportunities", [])}
    new_opps = sorted([key for key in curr_opp if key not in prev_opp])
    dropped_opps = sorted([key for key in prev_opp if key not in curr_opp])

    return {
        "status": "ok",
        "positions_delta": {
            "top_movers": movers[:3],
            "new_positions": new_positions,
            "removed_positions": removed_positions,
        },
        "radar_delta": {
            "new_opportunities": new_opps[:5],
            "dropped_opportunities": dropped_opps[:5],
        },
    }
