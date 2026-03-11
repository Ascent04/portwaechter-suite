from __future__ import annotations

from modules.v2.marketdata import batch_quotes


def test_failed_batch_symbol_is_retried_individually_when_batch_only_disabled(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []

    def _fake(symbols, api_key=None, cfg=None, live_fallback_limit=None):
        calls.append(list(symbols))
        if len(symbols) > 1:
            return [
                {"symbol": "ENR.DE", "status": "ok", "provider": "twelvedata"},
                {"symbol": "DEZ.DE", "status": "error", "provider": "none"},
            ]
        return [{"symbol": "DEZ.DE", "status": "ok", "provider": "twelvedata"}]

    monkeypatch.setattr(batch_quotes, "get_quotes_with_fallback", _fake)

    rows = batch_quotes.fetch_quotes_for_instruments(
        [
            {"symbol": "ENR.DE", "isin": "DE000ENER6Y0", "name": "Siemens Energy", "group": "holding", "weight_pct": 20.0},
            {"symbol": "DEZ.DE", "isin": "DE0006305006", "name": "DEUTZ", "group": "holding", "weight_pct": 5.0},
        ],
        {"app": {"root_dir": str(tmp_path)}, "v2": {"marketdata": {"batch_size": 8}}, "api_governor": {"batch_only": False}},
        api_key="token",
    )

    assert calls[0] == ["ENR.DE", "DEZ.DE"]
    assert calls[1] == ["DEZ.DE"]
    assert rows[1]["quote"]["status"] == "ok"
    assert rows[1]["quote"]["provider"] == "twelvedata"


def test_retry_is_limited_to_holdings_when_enabled(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []

    def _fake(symbols, api_key=None, cfg=None, live_fallback_limit=None):
        calls.append(list(symbols))
        return [{"symbol": symbol, "status": "error", "provider": "none"} for symbol in symbols]

    monkeypatch.setattr(batch_quotes, "get_quotes_with_fallback", _fake)

    batch_quotes.fetch_quotes_for_instruments(
        [
            {"symbol": "DEZ.DE", "isin": "DE0006305006", "name": "DEUTZ", "group": "holding", "weight_pct": 5.0},
            {"symbol": "RHM.DE", "isin": None, "name": "Rheinmetall", "group": "scanner", "weight_pct": 0},
        ],
        {
            "app": {"root_dir": str(tmp_path)},
            "v2": {"marketdata": {"batch_size": 8, "max_retry_symbols": 12}},
            "api_governor": {"batch_only": False},
        },
        api_key="token",
    )

    assert calls[0] == ["DEZ.DE", "RHM.DE"]
    assert calls[1] == ["DEZ.DE"]
    assert len(calls) == 2


def test_holdings_are_fetched_before_scanners(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []

    def _fake(symbols, api_key=None, cfg=None, live_fallback_limit=None):
        calls.append(list(symbols))
        return [{"symbol": symbol, "status": "ok", "provider": "twelvedata"} for symbol in symbols]

    monkeypatch.setattr(batch_quotes, "get_quotes_with_fallback", _fake)

    batch_quotes.fetch_quotes_for_instruments(
        [
            {"symbol": "RHM.DE", "group": "scanner", "weight_pct": 0},
            {"symbol": "DEZ.DE", "group": "holding", "weight_pct": 5.0},
            {"symbol": "ENR.DE", "group": "holding", "weight_pct": 20.0},
        ],
        {"app": {"root_dir": str(tmp_path)}, "v2": {"marketdata": {"batch_size": 8, "max_retry_symbols": 12}}},
        api_key="token",
    )

    assert calls[0] == ["ENR.DE", "DEZ.DE", "RHM.DE"]
