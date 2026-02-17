from __future__ import annotations


def compute_market_regime(positions: list[dict], holdings_signals: list[dict], cfg: dict) -> dict:
    regime_cfg = cfg.get("briefing", {}).get("morning", {}).get("regime", {})
    risk_on_min = int(regime_cfg.get("risk_on_min", 2))
    risk_off_min = int(regime_cfg.get("risk_off_min", 2))

    up_strong = sum(1 for s in holdings_signals if s.get("direction") == "up")
    down_strong = sum(1 for s in holdings_signals if s.get("direction") == "down")

    total = len(positions)
    pct_up = round(sum(1 for p in positions if float(p.get("pnl_pct") or 0) > 0) / total, 2) if total else 0.0

    if up_strong >= risk_on_min and up_strong > down_strong and pct_up >= 0.5:
        regime = "risk_on"
    elif down_strong >= risk_off_min and down_strong > up_strong and pct_up <= 0.7:
        regime = "risk_off"
    else:
        regime = "neutral"

    comment = (
        f"{regime}: UpStrong={up_strong}, DownStrong={down_strong}, "
        f"Breite={int(pct_up * 100)}%"
    )
    return {
        "regime": regime,
        "facts": {"up_strong": up_strong, "down_strong": down_strong, "pct_up": pct_up},
        "comment": comment,
    }
