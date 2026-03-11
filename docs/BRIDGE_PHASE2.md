# Bridge Phase 2

## Ablauf

1. SignalProposal-Dateien werden aus `data/integration/signal_proposals/` geladen.
2. Offensichtliche Duplikate werden entfernt.
3. Budget- und Risk-Regeln bewerten jedes Proposal.
4. Daraus entsteht ein Trade-Candidate.
5. APPROVED und REDUCED koennen als Telegram-Ticket gesendet werden.
6. Das Proposal wird danach in `consumed/` verschoben.

## Budget

- Hedge-Fund-Budget: 5000 EUR
- Maximale Positionen: 3
- Maximale Gesamtexponierung: 60 Prozent
- Maximales Risiko pro Trade: 1 Prozent

Sizing-Baender:

- hoch: 1000 bis 1500 EUR
- mittel: 750 bis 1000 EUR
- spekulativ: 0 bis 500 EUR

## Entscheidungen

- `APPROVED`: Signal und Budget sind im Rahmen
- `REDUCED`: nur reduzierte Groesse sinnvoll
- `REJECTED`: nicht weiter verfolgen

## Telegram-Tickets

- `TRADE-TICKET` fuer APPROVED
- `TRADE-TICKET` mit reduzierter Groesse fuer REDUCED
- `TRADE-KANDIDAT ABGELEHNT` fuer REJECTED

## Pfade

- Offene Proposals: `data/integration/signal_proposals/YYYYMMDD/`
- Verbrauchte Proposals: `data/integration/consumed/YYYYMMDD/`
- Trade-Candidates: `data/virus_bridge/trade_candidates/YYYYMMDD/`
- Offene Positionen fuer Exposure-Checks: `data/virus_bridge/open_positions.json`
