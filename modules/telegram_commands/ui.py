from __future__ import annotations

from modules.telegram_commands.dashboard import render_desk_card


MAIN_MENU_ROWS = [
    ["📊 Status", "💼 Portfolio"],
    ["📈 Execution", "🧠 Organism"],
    ["🎯 Proposals", "🎫 Tickets"],
    ["⚠ Warnlagen", "🛠 System"],
    ["❓ Hilfe", "⚙ Einstellungen"],
]

STATUS_MENU_ROWS = [
    ["📊 Status", "💼 Portfolio"],
    ["📈 Execution", "🧠 Organism"],
    ["🎯 Proposals", "🎫 Tickets"],
    ["⚠ Warnlagen", "🛠 System"],
    ["❓ Hilfe", "⚙ Einstellungen"],
]

SETTINGS_MENU_ROWS = [
    ["🔕 Ruhezeiten", "⏰ Voreröffnung"],
    ["📣 Alert-Profil", "🌍 Märkte"],
    ["💬 Sprache", "⬅ Zurück"],
]

TICKET_LIST_MENU_ROWS = [
    ["📂 Offen", "💸 Teilverkauft"],
    ["✅ Geschlossen", "❌ Abgelehnt"],
    ["⏳ Später", "⬅ Zurück"],
]

TICKET_ACTION_LABELS = {
    "BOUGHT": "✅ Gekauft",
    "NOT_BOUGHT": "❌ Nicht gekauft",
    "LATER": "⏳ Später",
    "DETAILS": "📄 Details",
    "PARTIAL_EXIT": "💸 Teilverkauft",
    "FULL_EXIT": "🛑 Komplett verkauft",
    "TARGET_HIT": "🎯 Ziel erreicht",
    "STOP_HIT": "⛔ Stop-Loss",
}

BUTTON_ROUTE_MAP = {
    "📊 Status": "ui:main",
    "💼 Portfolio": "/portfolio",
    "📈 Execution": "/execution",
    "🧠 Organism": "/organism",
    "🎯 Proposals": "/proposals",
    "🎫 Tickets": "/tickets",
    "⚠ Warnlagen": "ui:warnings",
    "🛠 System": "/status",
    "❓ Hilfe": "/help",
    "⚙ Einstellungen": "ui:settings_menu",
    "📈 Kaufen prüfen": "ui:buy",
    "📉 Verkaufen prüfen": "ui:sell",
    "🛡 Risiko reduzieren": "ui:risk",
    "✅ Halten": "ui:hold",
    "📋 Tickets": "ui:tickets_menu",
    "🧠 Top Ideen": "/top",
    "ℹ Hilfe": "/help",
    "📊 Systemstatus": "/status",
    "💼 Portfolio": "/portfolio",
    "📁 Offene Tickets": "ui:tickets_open",
    "📈 Tagesreport": "/execution",
    "📆 Wochenreport": "ui:weekly_report",
    "🔔 Alerts": "/alerts show",
    "🧩 Datenquellen": "ui:data_sources",
    "🔕 Ruhezeiten": "ui:quiet_hours",
    "⏰ Voreröffnung": "ui:premarket",
    "📣 Alert-Profil": "/alerts show",
    "🌍 Märkte": "ui:markets",
    "💬 Sprache": "ui:language",
    "♻ Reset": "ui:main",
    "📂 Offen": "ui:tickets_open",
    "💸 Teilverkauft": "ui:tickets_partial",
    "✅ Geschlossen": "ui:tickets_closed",
    "✅ Ausgeführt": "ui:tickets_executed",
    "❌ Abgelehnt": "ui:tickets_rejected",
    "⏳ Später": "ui:tickets_deferred",
    "⬅ Zurück": "ui:main",
}


def _copy_rows(rows: list[list[str]]) -> list[list[str]]:
    return [list(row) for row in rows]


def build_main_menu() -> list[list[str]]:
    return _copy_rows(MAIN_MENU_ROWS)


def build_ticket_buttons(ticket_id: str, mode: str = "default") -> list[list[str]]:
    rows: list[list[str]] = []
    if mode == "closed_market":
        rows.append([TICKET_ACTION_LABELS["LATER"], TICKET_ACTION_LABELS["DETAILS"]])
        rows.append(["🎫 Tickets", "📊 Status"])
        return rows
    if mode == "executed_position":
        rows.append([TICKET_ACTION_LABELS["PARTIAL_EXIT"], TICKET_ACTION_LABELS["FULL_EXIT"]])
        rows.append([TICKET_ACTION_LABELS["TARGET_HIT"], TICKET_ACTION_LABELS["STOP_HIT"]])
        rows.append([TICKET_ACTION_LABELS["DETAILS"], "⬅ Zurück"])
        return rows

    rows.append([TICKET_ACTION_LABELS["BOUGHT"], TICKET_ACTION_LABELS["NOT_BOUGHT"]])
    rows.append([TICKET_ACTION_LABELS["LATER"], TICKET_ACTION_LABELS["DETAILS"]])
    return rows


def build_status_menu() -> list[list[str]]:
    return _copy_rows(STATUS_MENU_ROWS)


def build_settings_menu() -> list[list[str]]:
    return _copy_rows(SETTINGS_MENU_ROWS)


def build_ticket_list_menu() -> list[list[str]]:
    return _copy_rows(TICKET_LIST_MENU_ROWS)


def main_menu_text(cfg: dict | None = None) -> str:
    return render_desk_card(cfg or {})


def status_menu_text(cfg: dict | None = None) -> str:
    return render_desk_card(cfg or {})


def settings_menu_text() -> str:
    return "Einstellungen\n\nBetrieb und Benachrichtigungen kurz steuern."


def ticket_list_menu_text() -> str:
    return "Tickets\n\nOffene, teilweise geschlossene und abgeschlossene Tickets."


def supported_ui_labels() -> set[str]:
    labels = set(BUTTON_ROUTE_MAP)
    labels.update(TICKET_ACTION_LABELS.values())
    labels.update(button for row in MAIN_MENU_ROWS + STATUS_MENU_ROWS + SETTINGS_MENU_ROWS + TICKET_LIST_MENU_ROWS for button in row)
    return labels


def route_button(text: str, context: str | None = None) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    if raw == TICKET_ACTION_LABELS["LATER"] and context == "tickets_menu":
        return "ui:tickets_deferred"
    return BUTTON_ROUTE_MAP.get(raw)


def ticket_action_name(text: str, context: str | None = None) -> str | None:
    raw = str(text or "").strip()
    if raw == TICKET_ACTION_LABELS["LATER"] and context == "tickets_menu":
        return None
    for action_name, label in TICKET_ACTION_LABELS.items():
        if raw == label:
            return action_name
    return None
