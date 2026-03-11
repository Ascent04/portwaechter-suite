from __future__ import annotations

from modules.telegram_commands.handlers import handle_alerts_thresholds_market


def _cfg(tmp_path):
    return {
        "app": {"root_dir": str(tmp_path), "timezone": "Europe/Berlin"},
        "marketdata_alerts": {"enabled": True, "group_defaults": {"holdings": {}, "radar": {}}},
        "alert_profiles": {"current": "normal", "profiles": {"normal": {}}},
    }


def test_alerts_thresholds_validation(tmp_path) -> None:
    cfg = _cfg(tmp_path)

    msg = handle_alerts_thresholds_market(["foo", "0.5"], cfg)
    assert "Zahlen" in msg or "Fehler" in msg

    msg = handle_alerts_thresholds_market(["0", "0.5"], cfg)
    assert "> 0" in msg

    msg = handle_alerts_thresholds_market(["off"], cfg)
    assert "off" in msg.lower()
