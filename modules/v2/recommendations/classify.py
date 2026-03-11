from __future__ import annotations

from datetime import date, datetime


MAX_QUOTE_AGE_DAYS = 3
SELL_THRESHOLD = 6.0
RISK_REDUCE_THRESHOLD = 5.0
HOLD_THRESHOLD = 4.0


def _parse_quote_date(value: object) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None

def _is_fresh_quote(candidate: dict) -> bool:
    quote_date = _parse_quote_date((candidate.get("quote") or {}).get("timestamp"))
    if quote_date is None:
        return False
    return (date.today() - quote_date).days <= MAX_QUOTE_AGE_DAYS


def _watch_candidate(candidate: dict, total: float, confidence: str, news_score: float, is_holding: bool, reasons: set[str]) -> bool:
    if not _is_fresh_quote(candidate):
        return False

    volume_score = float(candidate.get("scores", {}).get("volume", 0) or 0)
    if news_score > 0 and total >= 3:
        return True

    if confidence not in {"hoch", "mittel"}:
        return False

    if is_holding and total >= 5 and ("portfolio_priority" in reasons or volume_score > 0):
        return True
    if not is_holding and total >= 5 and (volume_score > 0 or news_score > 0):
        return True
    return False


def _holding_should_hold(candidate: dict, opp_score: dict, defense_score: dict) -> bool:
    if not _is_fresh_quote(candidate):
        return False
    total = float(opp_score.get("total_score", 0) or 0)
    reasons = {str(value) for value in opp_score.get("reasons", [])}
    quote = candidate.get("quote") or {}
    pct_change = float(quote.get("percent_change", 0) or 0)
    negative_hits = int(candidate.get("details", {}).get("news", {}).get("negative_hits", 0) or 0)
    sell_score = float(defense_score.get("sell_score", defense_score.get("defense_score", 0)) or 0)
    risk_reduce_score = float(defense_score.get("risk_reduce_score", defense_score.get("defense_score", 0)) or 0)
    weight = float((candidate.get("portfolio_context") or {}).get("weight_pct", candidate.get("weight_pct", 0)) or 0)
    concentration_risk = str((candidate.get("portfolio_context") or {}).get("concentration_risk") or "low").lower()
    regime = str(candidate.get("regime") or "").lower()

    if sell_score >= SELL_THRESHOLD or risk_reduce_score >= RISK_REDUCE_THRESHOLD:
        return False
    if pct_change <= -2.0 or negative_hits > 0:
        return False
    if regime == "risk_off" and weight > 15:
        return False
    if concentration_risk == "high" and weight > 15:
        return False
    if total >= HOLD_THRESHOLD and ("portfolio_priority" in reasons or candidate.get("portfolio_priority", 0) or candidate.get("group") == "holding"):
        return True
    return False


def classify_candidate(candidate: dict, opp_score: dict, defense_score: dict) -> str:
    total = float(opp_score.get("total_score", 0) or 0)
    confidence = str(opp_score.get("confidence") or "")
    defense = float(defense_score.get("defense_score", 0) or 0)
    sell_score = float(defense_score.get("sell_score", defense) or 0)
    risk_reduce_score = float(defense_score.get("risk_reduce_score", defense) or 0)
    news_score = float(candidate.get("scores", {}).get("news", 0) or 0)
    is_holding = candidate.get("group") == "holding"
    reasons = {str(value) for value in opp_score.get("reasons", [])}
    is_fresh = _is_fresh_quote(candidate)

    if is_holding and is_fresh and (sell_score >= SELL_THRESHOLD or risk_reduce_score >= RISK_REDUCE_THRESHOLD):
        return "DEFENSE"
    if is_holding and is_fresh and total >= 6 and confidence in {"hoch", "mittel"} and news_score > 0 and sell_score < SELL_THRESHOLD and risk_reduce_score < RISK_REDUCE_THRESHOLD:
        return "ACTION"
    if is_holding and _holding_should_hold(candidate, opp_score, defense_score):
        return "WATCH"
    if is_fresh and total >= 6 and confidence in {"hoch", "mittel"} and defense < 5 and (not is_holding or total >= 6.5):
        return "ACTION"
    if _watch_candidate(candidate, total, confidence, news_score, is_holding, reasons):
        return "WATCH"
    return "IGNORE"
