from __future__ import annotations

from datetime import datetime
from pathlib import Path

from modules.common.utils import read_json
from modules.virus_bridge.budget import get_budget_context, suggest_position_size
from modules.virus_bridge.data_quality import compute_quote_age_minutes, is_quote_fresh
from modules.virus_bridge.market_hours import get_market_status
from modules.virus_bridge.stop_loss import compute_risk_eur, compute_stop_distance_pct, derive_stop_loss
from modules.virus_bridge.tr_universe import is_tr_verified, resolve_tr_asset_meta


DEFAULT_MIN_REDUCED_SCORE = 6.0
DEFAULT_MIN_APPROVAL_SCORE = 6.5
DEFAULT_MIN_OPERATIONAL_SIZE_EUR = 500.0
DEFAULT_BORDERLINE_SIZE_MULTIPLIER = 0.85
DEFAULT_STALE_SIZE_MULTIPLIER = 0.75


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _open_positions(cfg: dict) -> list[dict]:
    path = _root_dir(cfg) / "data" / "virus_bridge" / "open_positions.json"
    if not path.exists():
        return []
    try:
        payload = read_json(path)
    except Exception:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("positions"), list):
        return payload["positions"]
    return []


def _position_exposure(position: dict) -> float:
    for key in ("suggested_eur", "size_eur", "market_value_eur", "exposure_eur"):
        if position.get(key) is not None:
            return float(position.get(key) or 0)
    return 0.0


def _clip_sizes(size_min: float, size_max: float, suggested: float, limit: float) -> tuple[float, float, float]:
    allowed = max(0.0, float(limit or 0))
    if allowed <= 0:
        return 0.0, 0.0, 0.0
    clipped_max = min(size_max, allowed)
    clipped_min = min(size_min, clipped_max)
    clipped_suggested = min(suggested, clipped_max)
    return round(clipped_min, 2), round(clipped_max, 2), round(clipped_suggested, 2)


def _proposal_now(signal_proposal: dict) -> datetime | None:
    raw = str(signal_proposal.get("timestamp") or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _quote(signal_proposal: dict) -> dict:
    value = signal_proposal.get("quote")
    return value if isinstance(value, dict) else {}


def _quote_price(quote: dict) -> float | None:
    for key in ("last_price", "price"):
        try:
            value = float(quote.get(key))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def _push(values: list[str], item: str) -> None:
    text = str(item or "").strip()
    if text and text not in values:
        values.append(text)


def _thresholds(cfg: dict) -> dict:
    bridge_cfg = cfg.get("virus_bridge") if isinstance(cfg, dict) else {}
    thresholds = bridge_cfg.get("thresholds") if isinstance(bridge_cfg, dict) else {}
    if not isinstance(thresholds, dict):
        thresholds = {}

    def _float(name: str, default: float) -> float:
        try:
            value = float(thresholds.get(name, default) or default)
        except (TypeError, ValueError):
            return default
        return round(value, 4) if value > 0 else default

    min_reduced = _float("min_reduced_score", DEFAULT_MIN_REDUCED_SCORE)
    min_approval = _float("min_approval_score", DEFAULT_MIN_APPROVAL_SCORE)
    if min_approval < min_reduced:
        min_approval = min_reduced
    return {
        "min_reduced_score": min_reduced,
        "min_approval_score": min_approval,
        "min_operational_size_eur": _float("min_operational_size_eur", DEFAULT_MIN_OPERATIONAL_SIZE_EUR),
        "borderline_size_multiplier": _float("borderline_size_multiplier", DEFAULT_BORDERLINE_SIZE_MULTIPLIER),
        "stale_size_multiplier": _float("stale_size_multiplier", DEFAULT_STALE_SIZE_MULTIPLIER),
    }


def _result(
    decision: str,
    reasons: list[str],
    risk_flags: list[str],
    verified: bool,
    market_status: dict,
    size_min: float,
    size_max: float,
    suggested: float,
    stop_loss_hint: str,
    stop_loss_price: float | None,
    stop_method: str | None,
    stop_distance_pct: float | None,
    risk_eur: float | None,
    quote_age_minutes: float | None,
    data_fresh: bool,
) -> dict:
    return {
        "decision": decision,
        "reasons": reasons,
        "risk_flags": risk_flags,
        "tr_verified": verified,
        "market_status": market_status,
        "size_min_eur": round(size_min, 2),
        "size_max_eur": round(size_max, 2),
        "suggested_eur": round(suggested, 2),
        "stop_loss_hint": stop_loss_hint,
        "stop_loss_price": stop_loss_price,
        "stop_method": stop_method,
        "stop_distance_pct": stop_distance_pct,
        "risk_eur": risk_eur,
        "quote_age_minutes": quote_age_minutes,
        "data_fresh": data_fresh,
    }


def evaluate_proposal(signal_proposal: dict, cfg: dict) -> dict:
    asset = signal_proposal.get("asset") or {}
    isin = str(asset.get("isin") or signal_proposal.get("isin") or "").strip().upper()
    symbol = str(asset.get("symbol") or signal_proposal.get("symbol") or "").strip().upper() or None
    asset_meta = resolve_tr_asset_meta(isin, symbol, cfg)
    verified = is_tr_verified(isin, symbol, cfg)
    proposal_now = _proposal_now(signal_proposal)
    market_status = get_market_status(asset_meta, proposal_now, cfg)
    quote = _quote(signal_proposal)
    entry_price = _quote_price(quote)
    stop_loss = derive_stop_loss(signal_proposal, quote, cfg)
    quote_age_minutes = compute_quote_age_minutes(quote, proposal_now, cfg)
    data_fresh = is_quote_fresh(quote, proposal_now, cfg)

    sizing = suggest_position_size(signal_proposal, cfg)
    size_min = float(sizing.get("size_min_eur", 0) or 0)
    size_max = float(sizing.get("size_max_eur", 0) or 0)
    suggested = float(sizing.get("suggested_eur", 0) or 0)

    reasons: list[str] = []
    risk_flags: list[str] = []
    decision = "APPROVED"

    if str(signal_proposal.get("classification") or "").upper() != "KAUFIDEE_PRUEFEN":
        return _result(
            "REJECTED",
            ["Falsche Klassifikation fuer die Risk-Pruefung"],
            ["wrong_classification"],
            verified,
            market_status,
            0.0,
            0.0,
            0.0,
            stop_loss["stop_loss_hint"],
            stop_loss["stop_loss_price"],
            stop_loss.get("stop_method"),
            None,
            None,
            quote_age_minutes,
            data_fresh,
        )

    if not verified:
        return _result(
            "REJECTED",
            ["Nicht bei Trade Republic verifiziert"],
            ["tr_unverified"],
            False,
            market_status,
            0.0,
            0.0,
            0.0,
            stop_loss["stop_loss_hint"],
            stop_loss["stop_loss_price"],
            stop_loss.get("stop_method"),
            None,
            None,
            quote_age_minutes,
            data_fresh,
        )

    score = float(signal_proposal.get("score", 0) or 0)
    signal_strength = str(signal_proposal.get("signal_strength") or "spekulativ").lower()
    market_regime = str(signal_proposal.get("market_regime") or "neutral").lower()
    budget = get_budget_context(cfg)
    positions = _open_positions(cfg)
    thresholds = _thresholds(cfg)

    if score < thresholds["min_reduced_score"]:
        if signal_strength == "spekulativ":
            _push(risk_flags, "signal_spekulativ")
            reasons = ["Spekulatives Signal unter Mindestscore"]
        else:
            reasons = ["Score unter Mindestniveau fuer den Desk"]
        return _result(
            "REJECTED",
            reasons,
            risk_flags + ["score_too_low"],
            verified,
            market_status,
            0.0,
            0.0,
            0.0,
            stop_loss["stop_loss_hint"],
            stop_loss["stop_loss_price"],
            stop_loss.get("stop_method"),
            None,
            None,
            quote_age_minutes,
            data_fresh,
        )

    if signal_strength == "spekulativ":
        _push(risk_flags, "signal_spekulativ")
        decision = "REDUCED"
        _push(reasons, "Spekulatives Signal nur reduziert pruefen")
        size_min, size_max, suggested = _clip_sizes(size_min, size_max, suggested, size_max * 0.6)

    if score < thresholds["min_approval_score"] and decision == "APPROVED":
        decision = "REDUCED"
        _push(risk_flags, "score_borderline")
        _push(reasons, "Score nur im Grenzbereich")
        size_min, size_max, suggested = _clip_sizes(
            size_min,
            size_max,
            suggested,
            max(thresholds["min_operational_size_eur"], suggested * thresholds["borderline_size_multiplier"]),
        )

    if market_regime == "defensiv":
        _push(risk_flags, "marktlage_defensiv")
        if decision != "REJECTED":
            decision = "REDUCED"
            _push(reasons, "Defensive Marktlage")
            size_min, size_max, suggested = _clip_sizes(size_min, size_max, suggested, max(suggested * 0.7, size_min))

    if len(positions) >= int(budget["max_positions"]):
        _push(reasons, "Maximale Positionszahl erreicht")
        _push(risk_flags, "max_positions")
        return _result(
            "REJECTED",
            reasons,
            risk_flags,
            verified,
            market_status,
            0.0,
            0.0,
            0.0,
            stop_loss["stop_loss_hint"],
            stop_loss["stop_loss_price"],
            stop_loss.get("stop_method"),
            None,
            None,
            quote_age_minutes,
            data_fresh,
        )

    current_exposure = sum(_position_exposure(position) for position in positions)
    max_exposure = float(budget["budget_eur"]) * float(budget["max_total_exposure_pct"]) / 100.0
    remaining_exposure = max_exposure - current_exposure
    if remaining_exposure <= 0:
        _push(reasons, "Keine freie Exposure mehr verfuegbar")
        _push(risk_flags, "max_exposure")
        return _result(
            "REJECTED",
            reasons,
            risk_flags,
            verified,
            market_status,
            0.0,
            0.0,
            0.0,
            stop_loss["stop_loss_hint"],
            stop_loss["stop_loss_price"],
            stop_loss.get("stop_method"),
            None,
            None,
            quote_age_minutes,
            data_fresh,
        )

    if suggested > remaining_exposure:
        _push(risk_flags, "exposure_tight")
        clipped_min, clipped_max, clipped_suggested = _clip_sizes(size_min, size_max, suggested, remaining_exposure)
        if clipped_suggested <= 0 or remaining_exposure < max(250.0, clipped_min):
            _push(reasons, "Freier Exposure-Raum reicht nicht aus")
            _push(risk_flags, "exposure_blocked")
            return _result(
                "REJECTED",
                reasons,
                risk_flags,
                verified,
                market_status,
                0.0,
                0.0,
                0.0,
                stop_loss["stop_loss_hint"],
                stop_loss["stop_loss_price"],
                stop_loss.get("stop_method"),
                None,
                None,
                quote_age_minutes,
                data_fresh,
            )
        decision = "REDUCED"
        _push(reasons, "Restbudget begrenzt die Groesse")
        size_min, size_max, suggested = clipped_min, clipped_max, clipped_suggested

    stop_distance_pct = compute_stop_distance_pct(entry_price, stop_loss["stop_loss_price"])
    risk_eur = compute_risk_eur(suggested, stop_distance_pct)

    if not data_fresh:
        _push(risk_flags, "quote_stale")
        _push(reasons, "Kursdaten nicht frisch")
        if decision == "APPROVED":
            decision = "REDUCED"
        size_min, size_max, suggested = _clip_sizes(
            size_min,
            size_max,
            suggested,
            max(thresholds["min_operational_size_eur"], suggested * thresholds["stale_size_multiplier"]),
        )
        risk_eur = compute_risk_eur(suggested, stop_distance_pct)

    if stop_loss["stop_loss_price"] is None:
        _push(risk_flags, "stop_loss_missing")
        _push(reasons, "Stop-Loss unklar")
        if decision == "APPROVED":
            decision = "REDUCED"

    if stop_distance_pct is None or risk_eur is None:
        _push(risk_flags, "risk_not_computable")
        _push(reasons, "Maximales Risiko nicht berechenbar")
        if decision == "APPROVED":
            decision = "REDUCED"

    max_risk_eur = float(budget["budget_eur"]) * float(budget["max_risk_per_trade_pct"]) / 100.0
    if stop_distance_pct not in (None, 0) and risk_eur is not None and risk_eur > max_risk_eur:
        allowed_size = max_risk_eur / (stop_distance_pct / 100.0)
        clipped_min, clipped_max, clipped_suggested = _clip_sizes(size_min, size_max, suggested, allowed_size)
        if clipped_suggested <= 0 or clipped_suggested < thresholds["min_operational_size_eur"]:
            _push(reasons, "Risiko pro Trade waere fuer die Restgroesse zu hoch")
            _push(risk_flags, "risk_budget_blocked")
            return _result(
                "REJECTED",
                reasons,
                risk_flags,
                verified,
                market_status,
                0.0,
                0.0,
                0.0,
                stop_loss["stop_loss_hint"],
                stop_loss["stop_loss_price"],
                stop_loss.get("stop_method"),
                stop_distance_pct,
                risk_eur,
                quote_age_minutes,
                data_fresh,
            )
        _push(risk_flags, "risk_budget_capped")
        _push(reasons, "Groesse an das Risikobudget angepasst")
        size_min, size_max, suggested = clipped_min, clipped_max, clipped_suggested

    if suggested > 0 and suggested < thresholds["min_operational_size_eur"]:
        _push(reasons, "Vorgeschlagene Groesse zu klein fuer ein operatives Ticket")
        _push(risk_flags, "size_too_small")
        return _result(
            "REJECTED",
            reasons,
            risk_flags,
            verified,
            market_status,
            0.0,
            0.0,
            0.0,
            stop_loss["stop_loss_hint"],
            stop_loss["stop_loss_price"],
            stop_loss.get("stop_method"),
            stop_distance_pct,
            risk_eur,
            quote_age_minutes,
            data_fresh,
        )

    risk_eur = compute_risk_eur(suggested, stop_distance_pct)

    if not bool(market_status.get("is_open")) and decision in {"APPROVED", "REDUCED"}:
        decision = "PENDING_MARKET_OPEN"
        _push(reasons, "Markt aktuell geschlossen")
        _push(risk_flags, "market_closed")

    if not reasons and decision == "APPROVED":
        _push(reasons, "Signalstaerke, Daten und Risiko liegen im Rahmen")

    return _result(
        decision,
        reasons,
        risk_flags,
        verified,
        market_status,
        size_min,
        size_max,
        suggested,
        str(stop_loss.get("stop_loss_hint") or "Stop-Loss manuell pruefen"),
        stop_loss.get("stop_loss_price"),
        stop_loss.get("stop_method"),
        stop_distance_pct,
        risk_eur,
        quote_age_minutes,
        data_fresh,
    )
