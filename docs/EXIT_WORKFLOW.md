## Exit Workflow

Der CB Fund Desk erfasst Ausstiege weiter manuell in Telegram.
Es gibt keine Auto-Orders und keine Broker-Calls.

### Status

- `OPEN`: Ticket ist offen, aber noch nicht gekauft.
- `EXECUTED`: Position wurde gekauft.
- `PARTIALLY_CLOSED`: Position wurde teilweise verkauft.
- `CLOSED`: Position wurde komplett verkauft.
- `REJECTED`: Ticket wurde nicht gekauft.
- `DEFERRED`: Ticket wurde vertagt.

### Exit-Gründe

- `STOP_LOSS`
- `TARGET_REACHED`
- `MANUAL_EXIT`
- `PARTIAL_TAKE_PROFIT`
- `RISK_REDUCTION`

### Datenpfade

- Ticketstatus: `data/virus_bridge/ticket_state.json`
- Käufe: `data/virus_bridge/executions/YYYYMMDD/execution_<ticket_id>.json`
- Ausstiege: `data/virus_bridge/exits/YYYYMMDD/exit_<ticket_id>_<timestamp>.json`
- Lifecycle: `data/virus_bridge/ticket_lifecycle/<ticket_id>.json`

### Teilverkauf

1. `💸 Teilverkauft`
2. Verkaufskurs eingeben
3. Verkaufsbetrag in EUR eingeben
4. Grund mit `1`, `2` oder `3` angeben

Bestätigung:

```text
Teilverkauf gespeichert:
Advanced Micro Devices
Verkaufskurs: 110.0
Verkaufsbetrag: 400.0 EUR
Ergebnis: 40.00 EUR / 10.00 %
```

### Komplettverkauf

1. `🛑 Komplett verkauft`
2. Verkaufskurs eingeben
3. Grund mit `1`, `2` oder `3` angeben

Bestätigung:

```text
Verkauf gespeichert:
Bayer AG
Verkaufskurs: 95.0
Ergebnis: -50.00 EUR / -5.00 %
```

### PnL-Logik

Long-Position:

`pnl_pct = (exit_price - entry_price) / entry_price * 100`

`pnl_eur = size_eur * pnl_pct / 100`

Bei Teilverkäufen wird die Restgröße im Ticketstatus reduziert.
