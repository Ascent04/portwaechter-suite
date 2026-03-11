from __future__ import annotations


def score_negative_momentum(quote: dict) -> dict:
    pct_change = quote.get("percent_change")
    if quote.get("status") != "ok" or pct_change is None:
        return {"score": 0.0, "status": "unavailable", "reason": None}
    move = float(pct_change)
    if move <= -4.0:
        return {"score": 4.5, "status": "ok", "reason": "negative_momentum_strong"}
    if move <= -2.0:
        return {"score": 2.5, "status": "ok", "reason": "negative_momentum_medium"}
    if move < 0:
        return {"score": 1.0, "status": "ok", "reason": "negative_momentum_light"}
    return {"score": 0.0, "status": "ok", "reason": None}


def _push_reason(target: list[str], value: str | None) -> None:
    text = str(value or "").strip()
    if text and text not in target:
        target.append(text)


def compute_defense_score(candidate: dict, regime: str, holding_weight: float) -> dict:
    weight = float(holding_weight or 0)
    negative_move = score_negative_momentum(candidate.get("quote") or {})
    portfolio_context = candidate.get("portfolio_context") or {}
    negative_hits = int(candidate.get("details", {}).get("news", {}).get("negative_hits", 0) or 0)
    news_drivers = {str(value or "") for value in (candidate.get("details", {}).get("news", {}).get("drivers", []) or [])}
    concentration_weight = float(portfolio_context.get("concentration_weight_pct", 0) or 0)

    sell_score = 0.0
    risk_reduce_score = 0.0
    sell_reasons: list[str] = []
    risk_reduce_reasons: list[str] = []
    combined_reasons: list[str] = []
    has_weakness = float(negative_move.get("score", 0) or 0) > 0 or negative_hits > 0

    sell_score += float(negative_move.get("score", 0) or 0)
    risk_reduce_score += min(2.0, float(negative_move.get("score", 0) or 0))
    _push_reason(combined_reasons, negative_move.get("reason"))
    if negative_move.get("score", 0) >= 2:
        _push_reason(sell_reasons, negative_move.get("reason"))
    elif negative_move.get("score", 0) > 0:
        _push_reason(risk_reduce_reasons, negative_move.get("reason"))

    news_reason = "news_burden" if negative_hits or {"negative_news", "news_burden"} & news_drivers else None
    if negative_hits >= 2:
        sell_score += 3.0
        risk_reduce_score += 2.0
        _push_reason(sell_reasons, news_reason)
        _push_reason(combined_reasons, news_reason)
    elif negative_hits == 1:
        sell_score += 1.5
        risk_reduce_score += 2.0
        _push_reason(risk_reduce_reasons, news_reason)
        _push_reason(combined_reasons, news_reason)

    if weight > 25:
        if has_weakness:
            sell_score += 2.5
            risk_reduce_score += 3.5
        else:
            risk_reduce_score += 1.0
        _push_reason(sell_reasons, "very_high_weight" if has_weakness else None)
        _push_reason(risk_reduce_reasons, "very_high_weight")
        _push_reason(combined_reasons, "very_high_weight")
    elif weight > 15:
        if has_weakness:
            sell_score += 1.5
            risk_reduce_score += 2.5
        else:
            risk_reduce_score += 0.75
        _push_reason(sell_reasons, "high_weight" if has_weakness else None)
        _push_reason(risk_reduce_reasons, "high_weight")
        _push_reason(combined_reasons, "high_weight")
    elif weight >= 8:
        risk_reduce_score += 1.5 if has_weakness else 0.5
        _push_reason(risk_reduce_reasons, "relevant_weight")
        _push_reason(combined_reasons, "relevant_weight")

    if concentration_weight >= 40:
        if has_weakness or regime == "risk_off":
            sell_score += 1.5 if has_weakness else 0.0
            risk_reduce_score += 2.0
            _push_reason(risk_reduce_reasons, "risk_concentration")
            _push_reason(combined_reasons, "risk_concentration")
    elif concentration_weight >= 25:
        if has_weakness or regime == "risk_off":
            risk_reduce_score += 1.5
            _push_reason(risk_reduce_reasons, "risk_concentration")
            _push_reason(combined_reasons, "risk_concentration")

    if regime == "risk_off":
        if has_weakness or weight > 15:
            sell_score += 1.0 if has_weakness else 0.0
            risk_reduce_score += 2.0
            _push_reason(risk_reduce_reasons, "risk_off_regime")
            _push_reason(combined_reasons, "risk_off_regime")
    elif regime == "neutral" and weight > 15:
        if has_weakness:
            risk_reduce_score += 1.0
            _push_reason(risk_reduce_reasons, "uncertain_regime")
            _push_reason(combined_reasons, "uncertain_regime")

    reasons = sell_reasons or risk_reduce_reasons or combined_reasons
    return {
        "defense_score": round(min(max(sell_score, risk_reduce_score), 10.0), 2),
        "sell_score": round(min(sell_score, 10.0), 2),
        "risk_reduce_score": round(min(risk_reduce_score, 10.0), 2),
        "reasons": reasons[:3],
        "sell_reasons": sell_reasons[:3],
        "risk_reduce_reasons": risk_reduce_reasons[:3],
    }
