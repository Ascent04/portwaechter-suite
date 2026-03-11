from __future__ import annotations


LONG_STRUCTURE_FIELDS = (
    ("structure_stop_price", "Stop-Loss an explizitem Struktur-Niveau pruefen"),
    ("last_pullback_low", "Stop-Loss unter letztem Ruecksetzer pruefen"),
    ("last_swing_low", "Stop-Loss unter letztem Swing-Tief pruefen"),
    ("support_level", "Stop-Loss unter Support pruefen"),
    ("day_low", "Stop-Loss unter Tagestief pruefen"),
)

SHORT_STRUCTURE_FIELDS = (
    ("structure_stop_price", "Stop-Loss an explizitem Struktur-Niveau pruefen"),
    ("last_pullback_high", "Stop-Loss ueber letztem Gegenlauf pruefen"),
    ("last_swing_high", "Stop-Loss ueber letztem Swing-Hoch pruefen"),
    ("resistance_level", "Stop-Loss ueber Widerstand pruefen"),
    ("day_high", "Stop-Loss ueber Tageshoch pruefen"),
)

DEFAULT_MIN_STRUCTURE_DISTANCE_PCT = 1.5
DEFAULT_MAX_STRUCTURE_DISTANCE_PCT = 6.0


def _direction(signal_proposal: dict) -> str:
    return str(signal_proposal.get("direction") or "long").strip().lower()


def _quote_price(quote: dict | None) -> float | None:
    if not isinstance(quote, dict):
        return None
    for key in ("last_price", "price"):
        try:
            value = float(quote.get(key))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def _safe_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _settings(cfg: dict | None) -> dict:
    if not isinstance(cfg, dict):
        return {}
    bridge = cfg.get("virus_bridge")
    if not isinstance(bridge, dict):
        return {}
    stop_cfg = bridge.get("stop_loss")
    return stop_cfg if isinstance(stop_cfg, dict) else {}


def _positive_float(value: object, default: float) -> float:
    parsed = _safe_float(value)
    return parsed if parsed is not None else default


def _structure_limits(cfg: dict) -> tuple[float, float]:
    stop_cfg = _settings(cfg)
    min_distance = _positive_float(stop_cfg.get("min_structure_distance_pct"), DEFAULT_MIN_STRUCTURE_DISTANCE_PCT)
    max_distance = _positive_float(stop_cfg.get("max_structure_distance_pct"), DEFAULT_MAX_STRUCTURE_DISTANCE_PCT)
    if min_distance >= max_distance:
        return DEFAULT_MIN_STRUCTURE_DISTANCE_PCT, DEFAULT_MAX_STRUCTURE_DISTANCE_PCT
    return round(min_distance, 4), round(max_distance, 4)


def _distance_pct(last_price: float, stop_price: float) -> float:
    return round(abs(last_price - stop_price) / last_price * 100.0, 4)


def _is_plausible_structure_stop(stop_price: float, last_price: float, direction: str, cfg: dict) -> bool:
    if direction == "short":
        if stop_price <= last_price:
            return False
    elif stop_price >= last_price:
        return False
    min_distance, max_distance = _structure_limits(cfg)
    distance = _distance_pct(last_price, stop_price)
    return min_distance <= distance <= max_distance


def _containers(signal_proposal: dict, quote: dict | None) -> list[dict]:
    details = signal_proposal.get("details")
    structure = signal_proposal.get("structure")
    technical = signal_proposal.get("technical")
    items = [
        signal_proposal,
        structure if isinstance(structure, dict) else {},
        technical if isinstance(technical, dict) else {},
        details if isinstance(details, dict) else {},
    ]
    if isinstance(details, dict):
        items.append(details.get("structure") if isinstance(details.get("structure"), dict) else {})
        items.append(details.get("technical") if isinstance(details.get("technical"), dict) else {})
    if isinstance(structure, dict):
        long_short = structure.get(_direction(signal_proposal))
        items.append(long_short if isinstance(long_short, dict) else {})
    items.append(quote if isinstance(quote, dict) else {})
    return [item for item in items if isinstance(item, dict)]


def _structure_stop(signal_proposal: dict, quote: dict | None, last_price: float, direction: str, cfg: dict) -> dict | None:
    fields = SHORT_STRUCTURE_FIELDS if direction == "short" else LONG_STRUCTURE_FIELDS
    for container in _containers(signal_proposal, quote):
        for field, hint in fields:
            value = _safe_float(container.get(field))
            if value is None:
                continue
            if not _is_plausible_structure_stop(value, last_price, direction, cfg):
                continue
            return {
                "stop_loss_hint": hint,
                "stop_loss_price": round(value, 2),
                "stop_method": "structure",
            }
    return None


def derive_stop_loss(signal_proposal: dict, quote: dict | None, cfg: dict) -> dict:
    direction = _direction(signal_proposal)
    last_price = _quote_price(quote)
    if last_price is None:
        return {"stop_loss_hint": "Stop-Loss manuell pruefen", "stop_loss_price": None, "stop_method": "manual"}

    structured = _structure_stop(signal_proposal, quote, last_price, direction, cfg)
    if structured:
        return structured

    if direction == "short":
        return {
            "stop_loss_hint": "Stop-Loss oberhalb des letzten Gegenlaufs pruefen",
            "stop_loss_price": round(last_price * 1.03, 2),
            "stop_method": "fallback",
        }

    return {
        "stop_loss_hint": "Stop-Loss unterhalb des letzten Ruecksetzers pruefen",
        "stop_loss_price": round(last_price * 0.97, 2),
        "stop_method": "fallback",
    }


def compute_stop_distance_pct(entry_price: float | None, stop_price: float | None) -> float | None:
    try:
        entry = float(entry_price)
        stop = float(stop_price)
    except (TypeError, ValueError):
        return None
    if entry <= 0:
        return None
    return round(abs(entry - stop) / entry * 100.0, 2)


def compute_risk_eur(size_eur: float | None, stop_distance_pct: float | None) -> float | None:
    try:
        size = float(size_eur)
        distance = float(stop_distance_pct)
    except (TypeError, ValueError):
        return None
    return round(size * (distance / 100.0), 2)
