from __future__ import annotations

from modules.telegram_commands.ui import (
    build_main_menu,
    build_settings_menu,
    build_status_menu,
    build_ticket_buttons,
    build_ticket_list_menu,
    route_button,
    supported_ui_labels,
)


def test_all_ui_labels_are_german_and_clean() -> None:
    labels = set()
    for rows in (build_main_menu(), build_status_menu(), build_settings_menu(), build_ticket_list_menu(), build_ticket_buttons("VF-1")):
        for row in rows:
            labels.update(row)

    assert "Watch" not in labels
    assert "Action" not in labels
    assert "Defense" not in labels
    assert "Confidence" not in labels
    assert "Regime" not in labels
    assert "Menu" not in labels
    assert "Back" not in labels
    assert "Settings" not in labels
    assert "📊 Status" in labels
    assert "⚙ Einstellungen" in labels
    assert "💼 Portfolio" in labels
    assert "📄 Details" in labels


def test_supported_labels_cover_main_actions() -> None:
    labels = supported_ui_labels()
    assert "📊 Status" in labels
    assert "💼 Portfolio" in labels
    assert "📈 Execution" in labels
    assert "🧠 Organism" in labels
    assert "🎯 Proposals" in labels
    assert "🎫 Tickets" in labels
    assert "⚠ Warnlagen" in labels
    assert "🛠 System" in labels
    assert "❓ Hilfe" in labels
    assert "⚙ Einstellungen" in labels
    assert "✅ Gekauft" in labels
    assert "💸 Teilverkauft" in labels
    assert "✅ Geschlossen" in labels


def test_ticket_bucket_buttons_route_to_lifecycle_views() -> None:
    assert route_button("💸 Teilverkauft", "tickets_menu") == "ui:tickets_partial"
    assert route_button("✅ Geschlossen", "tickets_menu") == "ui:tickets_closed"
    assert route_button("⏳ Später", "tickets_menu") == "ui:tickets_deferred"


def test_main_navigation_routes_cover_warning_and_system_views() -> None:
    assert route_button("⚠ Warnlagen", "main_menu") == "ui:warnings"
    assert route_button("🛠 System", "main_menu") == "/status"
