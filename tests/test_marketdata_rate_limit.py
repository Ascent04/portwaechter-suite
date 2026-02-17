from __future__ import annotations

from unittest.mock import patch

from modules.marketdata_watcher.adapter_http import fetch_stooq_latest


class _Resp:
    def __init__(self, body: str):
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


def test_fetch_stooq_latest_marks_rate_limited() -> None:
    with patch("modules.marketdata_watcher.adapter_http.request.urlopen", return_value=_Resp("Exceeded the daily hits limit")):
        out = fetch_stooq_latest("bas.de")
    assert out["status"] == "rate_limited"


def test_fetch_stooq_latest_provider_empty_for_blank() -> None:
    with patch("modules.marketdata_watcher.adapter_http.request.urlopen", return_value=_Resp("")):
        out = fetch_stooq_latest("bas.de")
    assert out["status"] == "provider_empty"
