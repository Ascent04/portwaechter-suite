# DAILY_DESK_RUNBOOK

Stand: 2026-03-11
Aktiver Produktivpfad: `/opt/portwaechter`

## Vor Handelsbeginn

1. Letzten Systemstand pruefen:
   - Telegram: `/status`
   - Telegram: `/portfolio`
   - Telegram: `/execution`
2. Offene Ideen und offene Tickets pruefen:
   - Telegram: `/proposals`
   - Telegram: `/tickets`
3. Wenn der Scanner oder die Bridge manuell angestossen werden muessen:
   ```bash
   cd /opt/portwaechter
   ./.venv/bin/python -m modules.v2.main run
   ./.venv/bin/python -m modules.virus_bridge.main run
   ./.venv/bin/python -m modules.telegram_commands.poller run
   ```
4. Vor Boersenstart keine Buy-Tickets als handlungsfaehig behandeln, wenn `Markt geschlossen`, `Frische Kursdaten` oder `Ticket-Reife` fehlen.

## Waehren des Handelstags

1. Nur diese Commands fuer die laufende Lage nutzen:
   - `/status`
   - `/portfolio`
   - `/execution`
   - `/proposals`
   - `/tickets`
2. Buy-Ticket nur dann manuell umsetzen, wenn Telegram als operativ nutzbar zeigt:
   - Einstieg vorhanden
   - Stop-Kurs vorhanden
   - Stop-Methode vorhanden
   - Stop-Abstand vorhanden
   - Risiko in EUR vorhanden
   - Positionsgroesse vorhanden
3. Ticket-Aktionen nur ueber den Telegram-Workflow erfassen:
   - Kauf: `✅ Gekauft`
   - Ablehnung: `❌ Nicht gekauft`
   - spaeter: `⏳ Später`
4. Offene Positionen und Exits nur ueber `/tickets` weiterfuehren:
   - Teilverkauf
   - Vollverkauf
   - Stop-Loss
   - Ziel erreicht

## Nach Handelsschluss

1. Execution-Wahrheit pruefen:
   - Telegram: `/execution`
2. Offene und teilweise geschlossene Positionen pruefen:
   - Telegram: `/tickets`
3. Wenn waehrend des Tages neue Proposals angefallen sind, den Bridge-Lauf abschliessen:
   ```bash
   cd /opt/portwaechter
   ./.venv/bin/python -m modules.virus_bridge.main run
   ./.venv/bin/python -m modules.telegram_commands.poller run
   ```
4. Wenn der Depotstand veraltet ist, neuen TR-PDF-Auszug hochladen oder in `data/inbox/` ablegen.

## Wichtige Commands

### Telegram

- `/status`  
  Systemlage, Warnungen, Betriebszustand
- `/portfolio`  
  letzter belastbarer Depotstand
- `/execution`  
  echte Ausfuehrungen, Teilverkaeufe, geschlossene Trades, Kostenstatus
- `/proposals`  
  offene Kaufideen und Ticket-Reife
- `/tickets`  
  offene Tickets und offene Positionen
- `/organism`  
  laufende Monatsbewertung
- `/help`  
  Kurzhilfe

### Lokal

```bash
cd /opt/portwaechter
./.venv/bin/python -m modules.v2.main run
./.venv/bin/python -m modules.virus_bridge.main run
./.venv/bin/python -m modules.telegram_commands.poller run
```

## Warnsignale

- `/status` meldet Warnlage oder API-Stress
- `/portfolio` meldet `veraltet`, `Datenqualitaet niedrig` oder `Kein bestaetigter Depotauszug`
- `/execution` meldet `Noch keine echten Ausfuehrungen`, `Kosten nicht gedeckt` oder unvollstaendige Exits
- `/proposals` oder `/tickets` zeigen `UNVOLLSTAENDIG`, `MARKT GESCHLOSSEN` oder `OPERATIV REDUZIERT`

## Was bei unvollstaendigen Signalen zu tun ist

1. Nicht kaufen.
2. Signal nur als Research-Hinweis behandeln.
3. In `/proposals` oder `/tickets` auf fehlende Felder achten:
   - Stop-Kurs
   - Stop-Methode
   - Stop-Abstand
   - Risiko
   - Positionsgroesse
   - Frische Kursdaten
   - Ticket-Reife
4. Erst nach neuem Scanner-/Bridge-Lauf erneut pruefen:
   ```bash
   cd /opt/portwaechter
   ./.venv/bin/python -m modules.v2.main run
   ./.venv/bin/python -m modules.virus_bridge.main run
   ```

## Was bei fehlenden Daten zu tun ist

1. Wenn `/portfolio` veraltet ist:
   - neuen TR-PDF-Auszug an den Bot senden
   - oder Datei in `data/inbox/` ablegen
2. Wenn `/execution` noch keine echten Trades zeigt:
   - keine Monats- oder Desk-Qualitaet aus Aktivitaet ableiten
3. Wenn Quotes stale sind:
   - kein Buy-Ticket manuell freigeben
   - Scanner spaeter erneut laufen lassen

## Was bei API- oder Betriebsstress zu tun ist

1. `/status` und `/status verbose` pruefen.
2. Keine manuellen Schnellschuesse aus alten Signalen machen.
3. Scanner-Lauf drosseln und nur bei Bedarf erneut ausfuehren:
   ```bash
   cd /opt/portwaechter
   ./.venv/bin/python -m modules.v2.main run
   ```
4. Danach nur die Bridge und den Telegram-Poller nachziehen:
   ```bash
   cd /opt/portwaechter
   ./.venv/bin/python -m modules.virus_bridge.main run
   ./.venv/bin/python -m modules.telegram_commands.poller run
   ```
5. Wenn `degraded` oder `blocked` wiederholt auftreten, den Tag defensiv weiterfuehren und keine Aktivitaet erzwingen.
