from __future__ import annotations

from modules.v2.marketdata import batch_quotes
from modules.v2.marketdata.provider_twelvedata import get_quotes_batch, search_symbol


def _cfg(tmp_path) -> dict:
    return {
        "app": {"root_dir": str(tmp_path)},
        "api_governor": {
            "enabled": True,
            "batch_only": True,
            "allow_symbol_search_runtime": False,
            "state_file": "data/api_governor/state.json",
            "metrics_file": "data/api_governor/usage_YYYYMMDD.jsonl",
        },
        "v2": {"marketdata": {"batch_size": 8}},
    }


def test_runtime_symbol_search_is_blocked(monkeypatch, tmp_path) -> None:
    called = {"value": False}

    def _fail(*args, **kwargs):
        called["value"] = True
        raise AssertionError("network should not be called")

    monkeypatch.setattr("modules.v2.marketdata.provider_twelvedata.request.urlopen", _fail)

    rows = search_symbol("AMD", "token", cfg=_cfg(tmp_path), runtime=True)

    assert rows == []
    assert called["value"] is False


def test_batch_only_blocks_single_scanner_quote(monkeypatch, tmp_path) -> None:
    called = {"value": False}

    def _fail(*args, **kwargs):
        called["value"] = True
        raise AssertionError("network should not be called")

    monkeypatch.setattr("modules.v2.marketdata.provider_twelvedata._request_quotes", _fail)

    rows = get_quotes_batch(["AMD"], "token", cfg=_cfg(tmp_path), context="scanner")

    assert rows[0]["status"] == "error"
    assert rows[0]["error"] == "batch_only_blocked"
    assert called["value"] is False


def test_batch_only_prevents_individual_retry_loop(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []

    def _fake(symbols, api_key=None, cfg=None, live_fallback_limit=None):
        calls.append(list(symbols))
        return [{"symbol": symbol, "status": "error", "provider": "none"} for symbol in symbols]

    monkeypatch.setattr(batch_quotes, "get_quotes_with_fallback", _fake)

    batch_quotes.fetch_quotes_for_instruments(
        [
            {"symbol": "DEZ.DE", "group": "holding", "weight_pct": 5.0},
            {"symbol": "RHM.DE", "group": "scanner", "weight_pct": 0.0},
        ],
        _cfg(tmp_path),
        api_key="token",
    )

    assert calls == [["DEZ.DE", "RHM.DE"]]
