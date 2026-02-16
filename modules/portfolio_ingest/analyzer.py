from __future__ import annotations

from typing import Any


REQUIRED_FIELDS = (
    "isin",
    "name",
    "quantity",
    "price_eur",
    "market_value_eur",
    "instrument_type",
)


def _sum_value(positions: list[dict[str, Any]]) -> float:
    return round(sum((pos.get("market_value_eur") or 0.0) for pos in positions), 2)


def _concentration(core_positions: list[dict[str, Any]], core_total: float) -> dict:
    sorted_core = sorted(core_positions, key=lambda p: p.get("market_value_eur") or 0.0, reverse=True)
    if core_total <= 0:
        return {"top1_pct": 0.0, "top3_pct": 0.0, "top5_pct": 0.0}

    def pct(top_n: int) -> float:
        value = sum((pos.get("market_value_eur") or 0.0) for pos in sorted_core[:top_n])
        return round((value / core_total) * 100, 2)

    return {
        "top1_pct": pct(1),
        "top3_pct": pct(3),
        "top5_pct": pct(5),
    }


def _missing_required_fields(positions: list[dict[str, Any]]) -> list[str]:
    missing: list[str] = []
    for idx, pos in enumerate(positions):
        for field in REQUIRED_FIELDS:
            value = pos.get(field)
            if value is None or value == "":
                missing.append(f"pos[{idx}].{field}")
    return missing


def analyze(snapshot: dict) -> dict:
    positions = snapshot.get("positions", [])
    total_value_eur = _sum_value(positions)

    core_positions = [
        pos for pos in positions if pos.get("instrument_type") in {"stock", "etf"}
    ]
    derivatives = [pos for pos in positions if pos.get("instrument_type") == "derivative"]

    core_total = _sum_value(core_positions)
    core_sorted = sorted(core_positions, key=lambda p: p.get("market_value_eur") or 0.0, reverse=True)

    top10_core = []
    for pos in core_sorted[:10]:
        value = pos.get("market_value_eur") or 0.0
        weight = round((value / core_total) * 100, 2) if core_total else 0.0
        top10_core.append({**pos, "weight_pct": weight})

    concentration = _concentration(core_positions, core_total)

    alerts = []
    if core_positions:
        alerts.append(
            {
                "id": "INFO_CONCENTRATION_TOP1",
                "value": concentration["top1_pct"],
                "message": f"Top-1 Konzentration (Core): {concentration['top1_pct']}%",
            }
        )

    if derivatives:
        alerts.append(
            {
                "id": "INFO_DERIVATIVES_PRESENT",
                "value": len(derivatives),
                "message": f"Derivate im Portfolio: {len(derivatives)}",
            }
        )

    missing = _missing_required_fields(positions)
    if missing:
        alerts.append(
            {
                "id": "DATA_QUALITY_MISSING_FIELDS",
                "value": len(missing),
                "message": "Fehlende Pflichtfelder in Snapshot-Positionen",
                "details": missing,
            }
        )

    return {
        "asof": snapshot.get("asof"),
        "base_currency": snapshot.get("base_currency", "EUR"),
        "total_value_eur": total_value_eur,
        "core_total_eur": core_total,
        "core_count": len(core_positions),
        "derivatives_count": len(derivatives),
        "top10_core": top10_core,
        "concentration": concentration,
        "alerts": alerts,
    }
