# Bridge Phase 1

## Zielbild

- Portwaechter V2 bleibt der Scanner- und Research-Layer.
- Virus Fund bleibt der Risk-, Audit- und Trade-Ticket-Layer.
- Nach aussen erscheint alles als ein gemeinsames System.
- Es gibt keine Auto-Trades und keine Broker-Calls.

## SignalProposal-Schema

Ein ACTION-Kandidat aus Portwaechter V2 wird als `KAUFIDEE_PRUEFEN` in eine Proposal-Datei geschrieben.

Wichtige Felder:

- `proposal_id`
- `source`
- `asset.symbol`
- `asset.isin`
- `asset.name`
- `classification`
- `direction`
- `score`
- `signal_strength`
- `market_regime`
- `reasons`
- `portfolio_context`
- `budget_context`
- `timestamp`

## Queue-Pfade

- Offene Proposals: `data/integration/signal_proposals/YYYYMMDD/`
- Verbrauchte Proposals: `data/integration/consumed/YYYYMMDD/`

## UX-Begriffe

- `WATCH` wird nach aussen zu `BEOBACHTEN`
- `ACTION` wird nach aussen zu `KAUFIDEE PRUEFEN`
- `DEFENSE` wird nach aussen zu `RISIKO PRUEFEN`
- `Confidence` wird nach aussen zu `Signalstaerke`
- `Regime` wird nach aussen zu `Marktlage`

## Befehle

- `/status`
- `/help`
- `/meaning`
- `/top`
- `/why <symbol|isin>`
- `/alerts`
- `/proposals`

## Warum nur ein Bot nach aussen

- Weniger doppelte Meldungen
- Ein gemeinsames Wording
- Klare Trennung nur intern
- Human-in-the-loop bleibt erhalten
