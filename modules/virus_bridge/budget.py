from __future__ import annotations


DEFAULTS = {
    "budget_eur": 5000,
    "max_positions": 3,
    "max_risk_per_trade_pct": 1.0,
    "max_total_exposure_pct": 60,
    "sizing": {
        "high_conf_min_eur": 1000,
        "high_conf_max_eur": 1500,
        "medium_conf_min_eur": 750,
        "medium_conf_max_eur": 1000,
        "speculative_min_eur": 0,
        "speculative_max_eur": 500,
    },
}


def _hedgefund_cfg(cfg: dict) -> dict:
    data = dict(DEFAULTS)
    raw = cfg.get("hedgefund", {}) if isinstance(cfg, dict) else {}
    data.update({key: value for key, value in raw.items() if key != "sizing"})
    sizing = dict(DEFAULTS["sizing"])
    sizing.update(raw.get("sizing", {}) if isinstance(raw.get("sizing"), dict) else {})
    data["sizing"] = sizing
    return data


def get_budget_context(cfg) -> dict:
    data = _hedgefund_cfg(cfg)
    return {
        "budget_eur": float(data.get("budget_eur", 5000) or 5000),
        "max_positions": int(data.get("max_positions", 3) or 3),
        "max_risk_per_trade_pct": float(data.get("max_risk_per_trade_pct", 1.0) or 1.0),
        "max_total_exposure_pct": float(data.get("max_total_exposure_pct", 60) or 60),
    }


def _range_for_signal_strength(signal_strength: str, cfg: dict) -> tuple[float, float]:
    sizing = _hedgefund_cfg(cfg)["sizing"]
    key = str(signal_strength or "spekulativ").strip().lower()
    if key == "hoch":
        return float(sizing["high_conf_min_eur"]), float(sizing["high_conf_max_eur"])
    if key == "mittel":
        return float(sizing["medium_conf_min_eur"]), float(sizing["medium_conf_max_eur"])
    return float(sizing["speculative_min_eur"]), float(sizing["speculative_max_eur"])


def suggest_position_size(signal_proposal: dict, cfg: dict) -> dict:
    if str(signal_proposal.get("classification") or "").upper() != "KAUFIDEE_PRUEFEN":
        return {"size_min_eur": 0.0, "size_max_eur": 0.0, "suggested_eur": 0.0}

    size_min, size_max = _range_for_signal_strength(signal_proposal.get("signal_strength"), cfg)
    score = float(signal_proposal.get("score", 0) or 0)
    midpoint = (size_min + size_max) / 2
    if score >= 8:
        suggested = (midpoint + size_max) / 2
    elif score >= 6:
        suggested = midpoint
    else:
        suggested = (size_min + midpoint) / 2

    return {
        "size_min_eur": round(size_min, 2),
        "size_max_eur": round(size_max, 2),
        "suggested_eur": round(suggested, 2),
    }
