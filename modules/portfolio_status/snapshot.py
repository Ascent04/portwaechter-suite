from __future__ import annotations

from datetime import datetime
from pathlib import Path

from modules.common.utils import read_json
from modules.virus_bridge.execution_performance import compute_open_trade_mark_to_market


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _parse_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        return parsed.astimezone().replace(tzinfo=None) if parsed.tzinfo else parsed
    return None


def _safe_float(value: object) -> float | None:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _latest_snapshot_path(cfg: dict) -> Path | None:
    root = _root_dir(cfg)
    candidates = list((root / "data" / "snapshots").glob("portfolio_*.json")) + list((root / "data" / "portfolio").glob("*.json"))
    files = [path for path in candidates if path.exists()]
    return max(files, key=lambda path: path.stat().st_mtime) if files else None


def _cash_from_snapshot(snapshot: dict) -> float | None:
    for key in ("cash_eur", "free_cash_eur", "cash_balance_eur", "available_cash_eur"):
        value = _safe_float(snapshot.get(key))
        if value is not None:
            return value
    return None


def _snapshot_positions(snapshot: dict, snapshot_ts: str) -> list[dict]:
    rows: list[dict] = []
    for row in snapshot.get("positions", []) if isinstance(snapshot.get("positions"), list) else []:
        if not isinstance(row, dict):
            continue
        price = _safe_float(row.get("price_eur") or row.get("market_price") or row.get("market_price_eur"))
        market_value = _safe_float(row.get("market_value_eur") or row.get("market_value"))
        rows.append(
            {
                "symbol": row.get("symbol") or row.get("isin"),
                "display_name": row.get("name") or row.get("display_name") or row.get("isin") or "Unbekannt",
                "quantity": _safe_float(row.get("quantity")),
                "average_entry_price": _safe_float(row.get("average_entry_price")),
                "market_price": price,
                "market_value": market_value,
                "source": "DEPOTAUSZUG",
                "last_updated_at": snapshot_ts,
            }
        )
    return rows


def _manual_positions(cfg: dict) -> list[dict]:
    rows: list[dict] = []
    for row in compute_open_trade_mark_to_market(cfg):
        entry_price = _safe_float(row.get("entry_price"))
        remaining = _safe_float(row.get("remaining_size_eur"))
        current_price = _safe_float(row.get("current_price"))
        quantity = round(remaining / entry_price, 6) if remaining and entry_price not in {None, 0} else None
        market_value = round(quantity * current_price, 2) if quantity and current_price is not None else remaining
        asset = row.get("asset") or {}
        rows.append(
            {
                "ticket_id": row.get("ticket_id"),
                "symbol": asset.get("symbol") or asset.get("isin") or row.get("ticket_id"),
                "display_name": asset.get("name") or asset.get("symbol") or row.get("ticket_id"),
                "quantity": quantity,
                "average_entry_price": entry_price,
                "market_price": current_price,
                "market_value": market_value,
                "source": "TELEGRAM_AUSFUEHRUNGEN",
                "last_updated_at": row.get("latest_exit_timestamp") or row.get("entry_timestamp"),
            }
        )
    return rows


def _position_key(row: dict) -> str:
    for key in ("symbol", "display_name", "ticket_id"):
        value = str(row.get(key) or "").strip().upper()
        if value:
            return value
    return "UNKNOWN"


def load_latest_portfolio_snapshot(cfg) -> dict | None:
    path = _latest_snapshot_path(cfg)
    if not path:
        return None
    try:
        payload = read_json(path)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    snapshot_ts = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
    gross = _safe_float(payload.get("computed_total_eur") or payload.get("pdf_total_value_eur"))
    positions = _snapshot_positions(payload, snapshot_ts)
    return {
        "snapshot_id": path.stem,
        "created_at": snapshot_ts,
        "source_type": "DEPOTAUSZUG",
        "source_details": {"path": str(path), "run_id": payload.get("run_id"), "validation_status": payload.get("validation_status")},
        "positions_count": len(positions),
        "gross_value_eur": gross if gross is not None else round(sum(_safe_float(row.get("market_value")) or 0 for row in positions), 2),
        "cash_eur": _cash_from_snapshot(payload),
        "positions": positions,
        "raw": payload,
    }


def load_manual_execution_count_since_snapshot(cfg, snapshot_ts) -> int:
    root = _root_dir(cfg) / "data" / "virus_bridge" / "executions"
    since_dt = _parse_timestamp(snapshot_ts)
    if not root.exists():
        return 0
    count = 0
    for path in sorted(root.rglob("execution_*.json")):
        try:
            payload = read_json(path)
        except Exception:
            continue
        executed_dt = _parse_timestamp(payload.get("executed_at")) or datetime.fromtimestamp(path.stat().st_mtime)
        if since_dt is None or executed_dt > since_dt:
            count += 1
    return count


def _freshness(source_type: str, snapshot_ts: str | None, manual_positions: list[dict]) -> str:
    times = [_parse_timestamp(snapshot_ts)] if snapshot_ts else []
    times.extend(_parse_timestamp(row.get("last_updated_at")) for row in manual_positions)
    latest = max((dt for dt in times if dt is not None), default=None)
    if latest is None:
        return "VERALTET"
    age_hours = max(0.0, (datetime.now() - latest).total_seconds() / 3600.0)
    if source_type == "DEPOTAUSZUG":
        return "AKTUELL" if age_hours <= 24 else ("TEILWEISE_AKTUELL" if age_hours <= 72 else "VERALTET")
    if source_type == "GEMISCHT":
        return "TEILWEISE_AKTUELL" if age_hours <= 72 else "VERALTET"
    return "TEILWEISE_AKTUELL" if age_hours <= 24 else "VERALTET"


def _confidence(source_type: str, freshness_status: str, positions_count: int) -> str:
    if positions_count == 0:
        return "NIEDRIG"
    if freshness_status == "VERALTET":
        return "NIEDRIG"
    if source_type == "DEPOTAUSZUG" and freshness_status == "AKTUELL":
        return "HOCH"
    if source_type in {"GEMISCHT", "TELEGRAM_AUSFUEHRUNGEN"}:
        return "MITTEL"
    return "MITTEL"


def _note(source_type: str, manual_count: int, merged_manual: int, conflicts: int, free_budget: float | None) -> str:
    if source_type == "DEPOTAUSZUG":
        return "Bestaende stammen aus dem letzten bestaetigten Snapshot."
    if source_type == "GEMISCHT":
        note = "Bestaende stammen aus dem letzten bestaetigten Snapshot. Einzelne Ausfuehrungen wurden zusaetzlich aus dem Lifecycle uebernommen."
        if conflicts > 0:
            note += " Nicht alle neueren Ausfuehrungen konnten positionsgenau mit dem Snapshot verrechnet werden."
        elif merged_manual > 0:
            note += f" {merged_manual} neue Positionen wurden zusaetzlich aus manuellen Ausfuehrungen ergaenzt."
        if free_budget is not None:
            note += " Das freie Budget ist als taktisches Desk-Budget abgeleitet."
        return note
    if source_type == "TELEGRAM_AUSFUEHRUNGEN":
        return "Es liegt kein bestaetigter Depotauszug vor. Der Stand basiert nur auf manuell erfassten Ausfuehrungen."
    return "Es liegt noch kein belastbarer Portfolio-Stand vor."


def build_portfolio_status(cfg) -> dict:
    raw_snapshot = load_latest_portfolio_snapshot(cfg)
    manual_positions = _manual_positions(cfg)
    manual_value = round(sum(_safe_float(row.get("market_value")) or 0 for row in manual_positions), 2) if manual_positions else None
    manual_snapshot = {row["ticket_id"]: row for row in manual_positions if row.get("ticket_id")}
    snapshot_ts = raw_snapshot.get("created_at") if raw_snapshot else None
    manual_count_since = load_manual_execution_count_since_snapshot(cfg, snapshot_ts)

    positions = list(raw_snapshot.get("positions", [])) if raw_snapshot else []
    gross_value = raw_snapshot.get("gross_value_eur") if raw_snapshot else None
    merged_manual = 0
    conflicts = 0
    seen = {_position_key(row) for row in positions}
    for row in manual_positions:
        key = _position_key(row)
        if raw_snapshot and key in seen:
            conflicts += 1
            continue
        positions.append(row)
        seen.add(key)
        merged_manual += 1
        if gross_value is not None and row.get("market_value") is not None:
            gross_value = round(gross_value + float(row["market_value"]), 2)

    if raw_snapshot and manual_count_since > 0:
        source_type = "GEMISCHT"
    elif raw_snapshot:
        source_type = "DEPOTAUSZUG"
    elif manual_positions:
        source_type = "TELEGRAM_AUSFUEHRUNGEN"
        gross_value = manual_value
    else:
        source_type = "UNBEKANNT"
        gross_value = None

    cash_eur = raw_snapshot.get("cash_eur") if raw_snapshot else None
    free_budget_eur = cash_eur
    if free_budget_eur is None and source_type in {"GEMISCHT", "TELEGRAM_AUSFUEHRUNGEN"}:
        budget = _safe_float(cfg.get("hedgefund", {}).get("budget_eur"))
        if budget is not None and manual_value is not None:
            free_budget_eur = round(max(0.0, budget - manual_value), 2)

    freshness_status = _freshness(source_type, snapshot_ts, manual_positions)
    confidence_status = _confidence(source_type, freshness_status, len(positions))
    return {
        "snapshot_id": raw_snapshot.get("snapshot_id") if raw_snapshot else None,
        "created_at": snapshot_ts or max((row.get("last_updated_at") for row in manual_positions), default=None),
        "source_type": source_type,
        "source_details": {
            "raw_snapshot": raw_snapshot.get("source_details") if raw_snapshot else None,
            "manual_positions_count": len(manual_positions),
            "manual_executions_since_snapshot": manual_count_since,
            "merged_manual_positions": merged_manual,
            "merge_conflicts": conflicts,
        },
        "freshness_status": freshness_status,
        "confidence_status": confidence_status,
        "positions_count": len(positions),
        "gross_value_eur": gross_value,
        "cash_eur": cash_eur,
        "free_budget_eur": free_budget_eur,
        "notes": _note(source_type, manual_count_since, merged_manual, conflicts, free_budget_eur if cash_eur is None else None),
        "positions": positions,
        "raw_source_snapshot": raw_snapshot,
        "derived_from_manual_positions": manual_snapshot,
    }
