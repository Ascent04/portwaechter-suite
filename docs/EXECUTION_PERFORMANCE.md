## Execution Performance

Der CB Fund Desk wertet reale, manuell erfasste Ausfuehrungen aus. Grundlage sind Entry-Daten aus `executions`, Exit-Dateien aus `exits`, Lifecycle-Dateien, Ticket-Status und die letzten verfuegbaren Quotes.

### Datenquellen

- `data/virus_bridge/executions/YYYYMMDD/`
- `data/virus_bridge/exits/YYYYMMDD/`
- `data/virus_bridge/ticket_lifecycle/`
- `data/virus_bridge/ticket_state.json`
- `data/virus_bridge/trade_candidates/YYYYMMDD/`
- optional aktuelle V2-Quotes aus `data/v2/candidates_*.json`

### Realisiert vs. unrealisiert

- Realisiert: bereits durch Teil- oder Vollverkauf festgeschrieben
- Unrealisiert: laufende Bewertung der verbleibenden Restgroesse

### Positionsklassen

- `OPEN`
- `PARTIALLY_CLOSED`
- `CLOSED`

### Kennzahlen

- Anzahl offener, teilweise verkaufter und geschlossener Positionen
- Summe realisierter PnL in EUR
- Summe unrealisierter PnL in EUR
- Durchschnitt offener PnL in Prozent
- Durchschnitt geschlossener PnL in Prozent
- Trefferquote geschlossener Trades
- beste und schwaechste geschlossene Position

### Mark-to-Market Grenzen

Wenn kein aktueller oder beurteilbarer Kurs vorliegt, wird die Position explizit als `price_unavailable` oder `stale` markiert. Es gibt keine stillen Annahmen ueber Live-Daten.

### Beispiel `/execution`

```text
CB Fund Desk - Ausfuehrungsstand

Offene Positionen: 1
Teilweise verkauft: 1
Geschlossen: 2

Realisiert: 180.00 EUR
Offen: 42.50 EUR

Trefferquote geschlossen: 50.00 %

Beste Position:
AMD 12.50 %

Schwaechste Position:
Bayer AG -4.00 %
```
