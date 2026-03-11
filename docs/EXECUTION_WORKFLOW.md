# Execution Workflow

CB Fund Desk bleibt im manuellen Modus. Es gibt keine Auto-Trades und keine Broker-Calls.

## Ticketstatus

- `OPEN`: Ticket ist aktiv und kann per Telegram bearbeitet werden.
- `EXECUTED`: Kauf wurde manuell bestaetigt und gespeichert.
- `REJECTED`: Ticket wurde als nicht gekauft markiert.
- `DEFERRED`: Ticket wurde auf spaeter gesetzt.
- `CLOSED`: spaetere manuelle Schliessung.

## Button-Aktionen

- `BOUGHT:<ticket_id>` startet die Eingabe fuer Kaufkurs und EUR-Einsatz.
- `NOT_BOUGHT:<ticket_id>` markiert das Ticket als abgelehnt.
- `LATER:<ticket_id>` setzt das Ticket auf spaeter.
- `DETAILS:<ticket_id>` sendet den vollen Tickettext erneut.

## Eingabefluss

1. `BOUGHT:<ticket_id>`
2. Bot fragt nach Kaufkurs.
3. Nutzer sendet nur die Zahl, z. B. `257.10`.
4. Bot fragt nach dem investierten EUR-Betrag.
5. Nutzer sendet nur die Zahl, z. B. `875`.
6. Das System schreibt einen Execution-Record und setzt den Ticketstatus auf `EXECUTED`.

## Datenpfade

- Ticket-State: `data/virus_bridge/ticket_state.json`
- Trade-Tickets: `data/virus_bridge/trade_candidates/YYYYMMDD/`
- Execution-Records: `data/virus_bridge/executions/YYYYMMDD/`
- Lifecycle: `data/virus_bridge/ticket_lifecycle/`

## Beispiel-Dialog

```text
BOUGHT:VF-20260309-2200-001

Zu welchem Kurs gekauft? Bitte nur Zahl senden, z. B. 257.10

257.10

Wie viel investiert? Bitte in EUR eingeben, z. B. 875

875

Ausfuehrung gespeichert:
Advanced Micro Devices
Kaufkurs: 257.1
Einsatz: 875.0 EUR
```
