from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json


def _root_dir(cfg: dict) -> Path:
    return Path(cfg.get("app", {}).get("root_dir", Path.cwd()))


def _universe_path(cfg: dict) -> Path:
    raw = cfg.get("virus_bridge", {}).get("tr_universe_path", "config/universe_tr_verified.json")
    path = Path(str(raw))
    return path if path.is_absolute() else _root_dir(cfg) / path


def load_tr_universe(cfg: dict) -> dict:
    path = _universe_path(cfg)
    if not path.exists():
        return {}
    try:
        payload = read_json(path)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def get_tr_asset_meta(isin: str, cfg: dict) -> dict | None:
    needle = str(isin or "").strip().upper()
    if not needle:
        return None
    value = load_tr_universe(cfg).get(needle)
    return dict(value) if isinstance(value, dict) else None


def _meta_by_symbol(symbol: str | None, cfg: dict) -> dict | None:
    needle = str(symbol or "").strip().upper()
    if not needle:
        return None
    for isin, value in load_tr_universe(cfg).items():
        if not isinstance(value, dict):
            continue
        if str(value.get("symbol") or "").strip().upper() != needle:
            continue
        return {"isin": isin, **value}
    return None


def is_tr_verified(isin: str, symbol: str | None, cfg: dict) -> bool:
    meta = get_tr_asset_meta(isin, cfg)
    if meta is None:
        meta = _meta_by_symbol(symbol, cfg)
    return bool((meta or {}).get("tr_verified") is True)


def resolve_tr_asset_meta(isin: str | None, symbol: str | None, cfg: dict) -> dict | None:
    meta = get_tr_asset_meta(str(isin or ""), cfg)
    if meta is not None:
        return {"isin": str(isin or "").strip().upper() or None, **meta}
    return _meta_by_symbol(symbol, cfg)
