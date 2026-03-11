from __future__ import annotations


def _concentration_context(candidate: dict, holding: dict, holdings: list[dict]) -> dict:
    cluster_field = "theme" if candidate.get("theme") or holding.get("theme") else "sector"
    cluster_value = candidate.get(cluster_field) or holding.get(cluster_field)
    cluster_weight = 0.0
    if cluster_value:
        cluster_weight = sum(
            float(row.get("weight_pct", 0) or 0)
            for row in holdings
            if (row.get(cluster_field) or "") == cluster_value
        )
    if cluster_weight >= 40:
        risk = "high"
    elif cluster_weight >= 25:
        risk = "medium"
    else:
        risk = "low"
    return {
        "cluster_field": cluster_field,
        "cluster_value": cluster_value,
        "concentration_weight_pct": round(cluster_weight, 2),
        "concentration_risk": risk,
    }


def compute_portfolio_priority(candidate: dict, holdings: list[dict]) -> float:
    identifier = str(candidate.get("isin") or candidate.get("symbol") or "")
    holding = next(
        (
            row
            for row in holdings
            if identifier
            and identifier in {str(row.get("isin") or ""), str(row.get("symbol") or "")}
        ),
        None,
    )
    if not holding:
        candidate["portfolio_context"] = {
            "is_holding": False,
            "weight_pct": float(candidate.get("weight_pct", 0) or 0),
            "concentration_weight_pct": 0.0,
            "concentration_risk": "low",
        }
        return 0.0

    weight = float(holding.get("weight_pct", 0) or 0)
    concentration = _concentration_context(candidate, holding, holdings)
    candidate["portfolio_context"] = {
        "is_holding": True,
        "weight_pct": round(weight, 2),
        **concentration,
    }
    score = 0.0
    if weight >= 15:
        score += 1.5
    elif weight >= 8:
        score += 1.0
    elif weight >= 3:
        score += 0.5

    cluster_weight = float(concentration.get("concentration_weight_pct", 0) or 0)
    if cluster_weight >= 40:
        score -= 0.9
    elif cluster_weight >= 25:
        score -= 0.45
    return round(score, 2)
