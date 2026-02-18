from __future__ import annotations

import json
from urllib.parse import parse_qs

from modules.telegram_commands import poller


class _Resp:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def read(self):
        return b'{"ok": true}'


def test_send_message_includes_persistent_reply_keyboard(monkeypatch) -> None:
    captured = {}

    def _fake_urlopen(req, timeout=0):
        payload = req.data.decode("utf-8")
        captured.update(parse_qs(payload))
        return _Resp()

    monkeypatch.setattr(poller.request, "urlopen", _fake_urlopen)

    cfg = {
        "telegram_commands": {
            "keyboard": {
                "enabled": True,
                "persistent": True,
                "resize": True,
                "rows": [["/status", "/alerts show"]],
            }
        }
    }

    ok = poller.send_message("token", "123", "hi", cfg)

    assert ok is True
    assert "reply_markup" in captured
    markup = json.loads(captured["reply_markup"][0])
    assert markup["is_persistent"] is True
    assert markup["keyboard"][0][0] == "/status"
