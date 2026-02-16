from __future__ import annotations

from typing import Any

from modules.common.config import load_config
from modules.common.utils import parse_de_number

DERIVATIVE_KEYWORDS = (
    "put",
    "call",
    "optionsschein",
    "knock-out",
    "vontobel",
    "warrant",
)


def _instrument_type(name: str) -> str:
    lowered = name.lower()
    if any(keyword in lowered for keyword in DERIVATIVE_KEYWORDS):
        return "derivative"
    if "etf" in lowered:
        return "etf"
    return "stock"


def _safe_parse(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return parse_de_number(str(value))
    except ValueError:
        return None


def _validation_tolerance() -> float:
    cfg = load_config()
    validation_cfg = cfg.get("portfolio", {}).get("validation", {})
    return float(validation_cfg.get("total_tolerance_eur", 0.50))


def normalize_snapshot(parsed: dict, base_currency: str = "EUR") -> dict:
    rows = parsed.get("rows", [])
    footer = parsed.get("footer", {})

    positions = []
    for row in rows:
        name_lines = row.get("name_lines") or []
        name = " ".join(name_lines).strip()

        position = {
            "isin": row.get("isin"),
            "name": name,
            "quantity": _safe_parse(row.get("qty_text")),
            "price_eur": _safe_parse(row.get("price_text")),
            "market_value_eur": _safe_parse(row.get("value_text")),
            "instrument_type": _instrument_type(name),
            "source": "tr_depotauszug_pdf",
        }
        positions.append(position)

    computed_total_eur = round(
        sum((pos.get("market_value_eur") or 0.0) for pos in positions),
        2,
    )

    snapshot = {
        "asof": parsed.get("asof"),
        "base_currency": base_currency,
        "positions": positions,
        "pdf_positions_count": footer.get("positions_count"),
        "pdf_total_value_eur": footer.get("total_value_eur"),
    }

    validation_status = "ok"
    pdf_positions_count = snapshot["pdf_positions_count"]
    pdf_total_value_eur = snapshot["pdf_total_value_eur"]

    if pdf_positions_count is not None and len(positions) != pdf_positions_count:
        validation_status = "degraded"

    if pdf_total_value_eur is None:
        validation_status = "degraded"
    else:
        diff = abs(computed_total_eur - float(pdf_total_value_eur))
        if diff > _validation_tolerance():
            raise ValueError("fail_validation_total")

    return {
        **snapshot,
        "computed_total_eur": computed_total_eur,
        "validation_status": validation_status,
    }
