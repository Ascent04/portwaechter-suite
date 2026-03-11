from __future__ import annotations

from modules.telegram_commands.ui import (
    build_main_menu,
    build_settings_menu,
    build_status_menu,
    build_ticket_buttons,
    build_ticket_list_menu,
    main_menu_text,
)


def test_main_menu_layout_matches_desk_order() -> None:
    assert build_main_menu() == [
        ["📊 Status", "💼 Portfolio"],
        ["📈 Execution", "🧠 Organism"],
        ["🎯 Proposals", "🎫 Tickets"],
        ["⚠ Warnlagen", "🛠 System"],
        ["❓ Hilfe", "⚙ Einstellungen"],
    ]


def test_ticket_buttons_are_compact_and_german() -> None:
    rows = build_ticket_buttons("VF-1")
    assert rows[0] == ["✅ Gekauft", "❌ Nicht gekauft"]
    assert rows[1] == ["⏳ Später", "📄 Details"]


def test_desk_navigation_is_consistent_across_main_and_status_menu() -> None:
    assert build_status_menu() == build_main_menu()
    assert build_settings_menu()[-1][-1] == "⬅ Zurück"
    assert build_ticket_list_menu() == [
        ["📂 Offen", "💸 Teilverkauft"],
        ["✅ Geschlossen", "❌ Abgelehnt"],
        ["⏳ Später", "⬅ Zurück"],
    ]


def test_main_menu_text_renders_compact_status_card(monkeypatch) -> None:
    monkeypatch.setattr(
        "modules.telegram_commands.ui.render_desk_card",
        lambda cfg: "CB Fund Desk\n\nDesk-Zustand:\n🟢 normal\n\nWarnlagen:\n🟢 normal",
    )

    text = main_menu_text({"app": {"timezone": "Europe/Berlin"}})

    assert "CB Fund Desk" in text
    assert "Desk-Zustand:" in text
    assert "Warnlagen:" in text
