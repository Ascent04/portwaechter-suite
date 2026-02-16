from __future__ import annotations

from modules.common.utils import now_iso_tz


def _weights(snapshot: dict) -> list[dict]:
    total = float(snapshot.get("computed_total_eur") or 0)
    positions = snapshot.get("positions", [])
    weighted: list[dict] = []

    for pos in positions:
        value = float(pos.get("market_value_eur") or 0)
        weight = (value / total * 100) if total > 0 else 0
        weighted.append({**pos, "weight_pct": round(weight, 2)})
    return weighted


def propose_rebalance(snapshot: dict, analysis: dict, cfg: dict) -> dict:
    rebalance_cfg = cfg.get("optimizer", {}).get("rebalance", {})
    max_position = float(rebalance_cfg.get("max_position_weight_pct", 20))
    max_top3 = float(rebalance_cfg.get("max_top3_weight_pct", 45))

    weighted = _weights(snapshot)
    actions: list[dict] = []
    rationale: list[str] = []

    action_by_isin: dict[str, dict] = {}

    for pos in weighted:
        isin = pos.get("isin")
        weight = float(pos.get("weight_pct") or 0)
        instrument_type = pos.get("instrument_type")

        if weight > max_position:
            action = {
                "type": "reduce",
                "isin": isin,
                "name": pos.get("name"),
                "target_weight_pct": max_position,
                "reason": f"Position weight {weight}% exceeds limit {max_position}%",
            }
            actions.append(action)
            action_by_isin[str(isin)] = action
            continue

        if instrument_type == "derivative":
            actions.append(
                {
                    "type": "hold",
                    "isin": isin,
                    "name": pos.get("name"),
                    "target_weight_pct": round(weight, 2),
                    "reason": "Derivative exposure monitored separately",
                }
            )

    top3_weight = float(analysis.get("concentration", {}).get("top3_pct", 0))
    if top3_weight > max_top3:
        rationale.append(f"Top-3 concentration {top3_weight}% exceeds limit {max_top3}%")
        core_sorted = sorted(
            [p for p in weighted if p.get("instrument_type") in {"stock", "etf"}],
            key=lambda row: float(row.get("weight_pct") or 0),
            reverse=True,
        )
        target_each = round(max_top3 / 3, 2)
        for pos in core_sorted[:3]:
            isin = str(pos.get("isin"))
            if isin in action_by_isin:
                continue
            actions.append(
                {
                    "type": "reduce",
                    "isin": pos.get("isin"),
                    "name": pos.get("name"),
                    "target_weight_pct": target_each,
                    "reason": "Reduce top-3 concentration",
                }
            )

    if not actions:
        first = weighted[0] if weighted else {}
        actions.append(
            {
                "type": "hold",
                "isin": first.get("isin"),
                "name": first.get("name", "n/a"),
                "target_weight_pct": float(first.get("weight_pct") or 0),
                "reason": "Portfolio within configured limits",
            }
        )

    return {
        "generated_at": now_iso_tz(),
        "limits": {
            "max_position_weight_pct": max_position,
            "max_top3_weight_pct": max_top3,
        },
        "actions": actions,
        "rationale": rationale,
    }
