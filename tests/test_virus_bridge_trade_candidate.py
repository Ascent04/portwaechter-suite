from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json
from modules.virus_bridge.ticket_render import render_ticket_text
from modules.virus_bridge.trade_candidate import build_trade_candidate, write_trade_candidate


def _cfg(tmp_path: Path) -> dict:
    return {"app": {"root_dir": str(tmp_path)}}


def _proposal() -> dict:
    return {
        "proposal_id": "PWV2-20260309-2100-001",
        "asset": {"symbol": "AMD", "isin": "US0079031078", "name": "Advanced Micro Devices"},
        "direction": "long",
        "quote": {"last_price": 197.69, "currency": "USD", "percent_change": 2.7},
        "signal_strength": "hoch",
        "market_regime": "positiv",
        "score": 7.2,
        "reasons": ["Momentum", "Ungewoehnlich hohes Volumen", "Positive Setup-Historie"],
        "entry_hint": "Einstieg nur bei weiter bestaetigter Staerke beobachten",
        "stop_loss_hint": "Stop-Loss unterhalb des letzten Ruecksetzers pruefen",
    }


def test_trade_candidate_is_built_written_and_rendered(tmp_path: Path) -> None:
    trade_candidate = build_trade_candidate(
        {**_proposal(), "_ticket_seq": 1},
        {
            "decision": "APPROVED",
            "reasons": ["Signalstaerke und Budget liegen im Rahmen"],
            "risk_flags": [],
            "size_min_eur": 1000,
            "size_max_eur": 1500,
            "suggested_eur": 1250,
            "stop_loss_hint": "Stop-Loss unterhalb des letzten Ruecksetzers pruefen",
            "stop_loss_price": 191.76,
            "stop_method": "fallback",
            "stop_distance_pct": 3.0,
            "risk_eur": 37.5,
            "quote_age_minutes": 0.0,
            "data_fresh": True,
        },
        _cfg(tmp_path),
    )
    path = Path(write_trade_candidate(trade_candidate, _cfg(tmp_path)))
    text = render_ticket_text(trade_candidate)

    assert trade_candidate["ticket_id"].startswith("VF-")
    assert path.exists()
    payload = read_json(path)
    assert payload["decision"] == "APPROVED"
    assert payload["last_price"] == 197.69
    assert payload["currency"] == "USD"
    assert payload["entry_hint"] == "Einstieg nur bei weiter bestaetigter Staerke beobachten"
    assert payload["stop_loss_hint"] == "Stop-Loss unterhalb des letzten Ruecksetzers pruefen"
    assert payload["stop_loss_price"] == 191.76
    assert payload["stop_method"] == "fallback"
    assert payload["stop_distance_pct"] == 3.0
    assert payload["risk_eur"] == 37.5
    assert payload["operational_status"] == "OPERATIV_NUTZBAR"
    assert payload["operational_is_actionable"] is True
    assert "KAUFEN PRUEFEN: Advanced Micro Devices" in text
    assert "Letzter Kurs:\n197.69 USD" in text
    assert "Positionsgroesse:\nMittlere bis groessere Positionsgroesse pruefen. Vorschlag: 1.000 bis 1.500 EUR." in text
    assert "Einstieg:\nEinstieg nur bei weiter bestaetigter Staerke beobachten" in text
    assert "Stop-Loss:\nStop-Loss unterhalb des letzten Ruecksetzers pruefen" in text
    assert "Stop-Kurs: 191.76" in text
    assert "Stop-Methode: fallback" in text
    assert "Maximales Risiko:\n37,50 EUR" in text
    assert len(text) < 1500


def test_trade_candidate_render_omits_missing_price_cleanly(tmp_path: Path) -> None:
    trade_candidate = build_trade_candidate(
        {
            "proposal_id": "PWV2-20260309-2100-002",
            "asset": {"symbol": "BAYN.DE", "isin": "DE000BAY0017", "name": "Bayer AG"},
            "direction": "long",
            "quote": {"last_price": None, "currency": None},
            "signal_strength": "mittel",
            "market_regime": "neutral",
            "score": 6.1,
            "reasons": ["Momentum"],
            "entry_hint": "Nur bei bestaetigter Staerke beobachten",
            "stop_hint": "Stop-Idee manuell pruefen",
            "_ticket_seq": 2,
        },
        {
            "decision": "REDUCED",
            "reasons": ["Restbudget begrenzt die Groesse"],
            "risk_flags": ["exposure_tight"],
            "size_min_eur": 750,
            "size_max_eur": 900,
            "suggested_eur": 750,
            "stop_loss_hint": "Stop-Loss manuell pruefen",
            "stop_loss_price": None,
            "stop_distance_pct": None,
            "risk_eur": None,
            "quote_age_minutes": None,
            "data_fresh": False,
        },
        _cfg(tmp_path),
    )

    text = render_ticket_text(trade_candidate)

    assert trade_candidate["operational_is_actionable"] is False
    assert "KAUFIDEE UEBERPRUEFEN: Bayer AG" in text
    assert "Operative Luecken:" in text


def test_reduced_candidate_with_stale_data_is_not_operational(tmp_path: Path) -> None:
    trade_candidate = build_trade_candidate(
        {**_proposal(), "_ticket_seq": 3},
        {
            "decision": "REDUCED",
            "reasons": ["Kursdaten nicht frisch", "Score nur im Grenzbereich"],
            "risk_flags": ["quote_stale", "score_borderline"],
            "size_min_eur": 937.5,
            "size_max_eur": 937.5,
            "suggested_eur": 937.5,
            "stop_loss_hint": "Stop-Loss unterhalb des letzten Ruecksetzers pruefen",
            "stop_loss_price": 191.76,
            "stop_method": "fallback",
            "stop_distance_pct": 3.0,
            "risk_eur": 28.13,
            "quote_age_minutes": 40.0,
            "data_fresh": False,
        },
        _cfg(tmp_path),
    )

    text = render_ticket_text(trade_candidate)

    assert trade_candidate["operational_is_actionable"] is False
    assert "KAUFIDEE UEBERPRUEFEN: Advanced Micro Devices" in text
    assert "Frische Kursdaten" in text
    assert "Ticket-Reife" in text
