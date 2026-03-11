from __future__ import annotations

import json

from modules.v2.symbols import build_missing_mapping_report, load_symbol_map, resolve_isin


def test_mapping_works(tmp_path) -> None:
    path = tmp_path / "symbol_map_v2.json"
    path.write_text(
        json.dumps({"DE000ENER6Y0": {"symbol": "ENR.DE", "provider": "twelvedata", "name": "Siemens Energy AG"}}),
        encoding="utf-8",
    )

    mapping = load_symbol_map(path=path)
    resolved = resolve_isin("DE000ENER6Y0", path=path)

    assert "DE000ENER6Y0" in mapping
    assert resolved == {"symbol": "ENR.DE", "provider": "twelvedata", "name": "Siemens Energy AG", "sector": None, "theme": None, "country": None, "status": "ok"}


def test_missing_mapping_handled(tmp_path) -> None:
    path = tmp_path / "symbol_map_v2.json"
    path.write_text(json.dumps({"DE000ENER6Y0": {"symbol": "ENR.DE"}}), encoding="utf-8")

    report = build_missing_mapping_report(
        [
            {"isin": "DE000ENER6Y0", "name": "Siemens Energy", "group": "holding"},
            {"isin": "US0000000000", "name": "Missing Inc.", "group": "holding"},
        ],
        path=path,
    )

    assert report["missing_count"] == 1
    assert report["missing"][0]["isin"] == "US0000000000"


def test_provider_unavailable_is_not_treated_as_missing(tmp_path) -> None:
    path = tmp_path / "symbol_map_v2.json"
    path.write_text(
        json.dumps({"DE000VK7S5D5": {"symbol": None, "provider": "provider_unavailable", "name": "Warrant", "status": "unsupported"}}),
        encoding="utf-8",
    )

    resolved = resolve_isin("DE000VK7S5D5", path=path)
    report = build_missing_mapping_report([{"isin": "DE000VK7S5D5", "name": "Warrant", "group": "holding"}], path=path)

    assert resolved == {"symbol": None, "provider": "provider_unavailable", "name": "Warrant", "sector": None, "theme": None, "country": None, "status": "unsupported"}
    assert report["missing_count"] == 0
