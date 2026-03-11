# SYSTEM_OVERVIEW

Stand: 2026-03-10
Aktiver Produktivpfad: `/opt/portwaechter`

## 1. Zweck des Systems

Das System bildet einen kleinen, file-basierten, manuell gefuehrten Desk ab.

Aktiver Ablauf:

`Twelve Data -> PortWaechter V2 -> SignalProposal -> Virus Bridge -> TradeCandidate/Ticket -> Telegram -> manuelle Ausfuehrung -> Lifecycle / Execution / Audit -> Monatsbewertung`

Ziel ist nicht Auto-Trading, sondern:

- operativ nutzbare Signale
- manuelle Freigabe und manuelle Ausfuehrung
- belastbare Ticket-, Exit- und PnL-Wahrheit
- ehrliche Sicht auf Kosten und wirtschaftliche Wirkung

## 2. Systemgrenzen

Harte Grenzen im aktuellen Code:

- keine Broker-Integration
- keine Auto-Trades
- Human-in-the-loop fuer Kauf, Teilverkauf, Vollverkauf und Ablehnung
- Telegram ist Bedienoberflaeche, nicht Ausfuehrungsautomat
- keine zweite Scannerwelt ausserhalb von `modules/v2/`
- keine Fantasie-Werte fuer Stop, Risiko, PnL oder Exit-Gruende

## 3. Hauptarchitektur

### PortWaechter V2

Zustaendig fuer Markt- und Signalvorstufe.

Wichtige Module:

- `modules/v2/main.py`
- `modules/v2/telegram/help.py`
- `modules/v2/recommendations/render.py`
- `modules/v2/marketdata/provider_twelvedata.py`

Wichtige Funktionen:

- `run()` in `modules/v2/main.py`
- `render_help_text()` in `modules/v2/telegram/help.py`

### Integration / Proposal Queue

Zustaendig fuer den Export von V2-Signalen in die Bridge.

Wichtige Module:

- `modules/integration/pw_to_virus.py`
- `modules/integration/virus_inbox.py`

Wichtige Funktionen:

- `build_signal_proposal()`
- `write_signal_proposal()`
- `export_action_candidates_to_bridge()`
- `load_pending_signal_proposals()`
- `mark_proposal_consumed()`

### Virus Bridge

Zustaendig fuer Intake, Risiko, Ticket-Erzeugung und Telegram-Sendung.

Wichtige Module:

- `modules/virus_bridge/main.py`
- `modules/virus_bridge/intake.py`
- `modules/virus_bridge/risk_eval.py`
- `modules/virus_bridge/stop_loss.py`
- `modules/virus_bridge/trade_candidate.py`
- `modules/virus_bridge/ticket_render.py`

Wichtige Funktionen:

- `run()` in `modules/virus_bridge/main.py`
- `evaluate_proposal()` in `modules/virus_bridge/risk_eval.py`
- `derive_stop_loss()` in `modules/virus_bridge/stop_loss.py`
- `build_trade_candidate()` in `modules/virus_bridge/trade_candidate.py`

### Lifecycle / Audit

Zustaendig fuer Ticket-Zustand, Events, Audit-Referenzen und Exit-Flow.

Wichtige Module:

- `modules/virus_bridge/lifecycle.py`
- `modules/virus_bridge/execution_workflow.py`
- `modules/virus_bridge/exit_flow.py`
- `modules/virus_bridge/audit_adapter.py`

Wichtige Funktionen:

- `record_ticket_lifecycle_event()`
- `render_tickets_text()`
- `mark_partial_exit()`
- `mark_full_exit()`

### Portfolio-Status

Zustaendig fuer den aktuellen Depotstand aus Snapshot plus manuellen Ausfuehrungen.

Wichtige Module:

- `modules/portfolio_status/snapshot.py`
- `modules/portfolio_status/status.py`

Wichtige Funktionen:

- `build_portfolio_status()`
- `render_portfolio_status()`

### Execution-Status

Zustaendig fuer offene Positionen, geschlossene Trades, Teilverkaeufe, PnL und Kostenstatus.

Wichtige Module:

- `modules/virus_bridge/execution_performance.py`
- `modules/virus_bridge/execution_report.py`
- `modules/virus_bridge/cost_status.py`

Wichtige Funktionen:

- `_build_all_positions()`
- `compute_execution_summary()`
- `build_execution_report()`
- `render_execution_summary()`
- `build_cost_status()`

### Organism- / Monatsbewertung

Zustaendig fuer die Monatsbewertung des Desks.

Wichtige Module:

- `modules/organism/monthly_evaluation.py`
- `modules/organism/report_render.py`

Wichtige Funktionen:

- `build_monthly_evaluation()`
- `evaluate_organism()`
- `render_organism_text()`

### Telegram-Bedienoberflaeche

Zustaendig fuer Command-Poller, Menues und Operator-UX.

Wichtige Module:

- `modules/telegram_commands/poller.py`
- `modules/telegram_commands/handlers.py`
- `modules/telegram_commands/ui.py`

Wichtige Funktionen:

- `run()` in `modules/telegram_commands/poller.py`
- `handle_command()`
- `status_text()`
- `portfolio_text()`

## 4. Datenfluss

Technischer Hauptfluss im aktiven Strang:

1. `modules/v2/main.py` erzeugt Empfehlungen.
2. `modules/integration/pw_to_virus.py` schreibt `SignalProposal`-JSON in die Bridge-Queue.
3. `modules/virus_bridge/main.py` laedt Pending-Proposals.
4. `modules/virus_bridge/risk_eval.py` bewertet Proposal, Marktstatus, TR-Verifikation, Budget, Stop und Risiko.
5. `modules/virus_bridge/trade_candidate.py` schreibt `TradeCandidate`-JSON.
6. `modules/virus_bridge/main.py` sendet operative oder informative Tickets an Telegram.
7. `modules/telegram_commands/poller.py` verarbeitet `/tickets`, `/execution`, `/portfolio`, `/organism` sowie Ticket-Aktionen.
8. `modules/virus_bridge/execution_workflow.py` speichert manuelle Ausfuehrungen.
9. `modules/virus_bridge/exit_flow.py` speichert Teilverkaeufe und Vollschliessungen.
10. `modules/virus_bridge/lifecycle.py` und `modules/virus_bridge/audit_adapter.py` halten Event- und Audit-Spur.
11. `modules/virus_bridge/execution_report.py` und `modules/organism/monthly_evaluation.py` bauen daraus Execution- und Monatswahrheit.

## 5. Source of Truth je Bereich

### Signale / Proposals

- Queue: `data/integration/signal_proposals/YYYYMMDD/`
- Verbraucht: `data/integration/consumed/YYYYMMDD/`
- Schreiblogik: `modules/integration/pw_to_virus.py`
- Leselogik: `modules/integration/virus_inbox.py`

### Trade Candidates / Tickets

- Dateien: `data/virus_bridge/trade_candidates/YYYYMMDD/ticket_<ticket_id>.json`
- Builder: `modules/virus_bridge/trade_candidate.py`
- Lifecycle-Start: `modules/virus_bridge/main.py`

### Ticket-Zustand / Lifecycle

- Ticket-Status: `data/virus_bridge/ticket_state.json`
- Lifecycle-Dateien: `data/virus_bridge/ticket_lifecycle/<ticket_id>.json`
- Event-Schreiber: `record_ticket_lifecycle_event()` in `modules/virus_bridge/lifecycle.py`

### Executions / Exits

- Ausfuehrungen: `data/virus_bridge/executions/YYYYMMDD/execution_<ticket_id>.json`
- Exits: `data/virus_bridge/exits/YYYYMMDD/exit_<ticket_id>_<timestamp>.json`
- Schreiblogik: `modules/virus_bridge/execution_workflow.py` und `modules/virus_bridge/exit_flow.py`

### Audit

- Audit-Log: `data/audit/portfolio_audit.jsonl`
- Adapter: `modules/virus_bridge/audit_adapter.py`

### Portfolio-Stand

- Bestaetigter Snapshot: `data/snapshots/portfolio_*.json` oder `data/portfolio/*.json`
- Manueller Overlay: offene Positionen aus `compute_open_trade_mark_to_market()`
- Builder: `build_portfolio_status()` in `modules/portfolio_status/snapshot.py`

### Execution- und PnL-Wahrheit

- Rekonstruktion: `_build_all_positions()` in `modules/virus_bridge/execution_performance.py`
- Aggregation: `build_execution_report()` in `modules/virus_bridge/execution_report.py`
- Kostenstatus: `build_cost_status()` in `modules/virus_bridge/cost_status.py`

### Monatsbewertung

- Monatsreport: `data/organism/monthly/monthly_evaluation_<YYYY_MM>.json`
- Builder: `build_monthly_evaluation()` in `modules/organism/monthly_evaluation.py`

## 6. Wichtige Pfade

Konfiguriert in `config/config.yaml` oder direkt im Code verwendet:

- `/opt/portwaechter/config/config.yaml`
- `/opt/portwaechter/data/integration/signal_proposals/`
- `/opt/portwaechter/data/integration/consumed/`
- `/opt/portwaechter/data/virus_bridge/trade_candidates/`
- `/opt/portwaechter/data/virus_bridge/ticket_state.json`
- `/opt/portwaechter/data/virus_bridge/ticket_lifecycle/`
- `/opt/portwaechter/data/virus_bridge/executions/`
- `/opt/portwaechter/data/virus_bridge/exits/`
- `/opt/portwaechter/data/virus_bridge/performance/`
- `/opt/portwaechter/data/audit/portfolio_audit.jsonl`
- `/opt/portwaechter/data/organism/monthly/`
- `/opt/portwaechter/data/snapshots/`
- `/opt/portwaechter/data/telegram/`

## 7. Wichtige Commands

Telegram-Commands aus `modules/telegram_commands/poller.py`:

- `/status`
- `/status verbose`
- `/portfolio`
- `/execution`
- `/proposals`
- `/tickets`
- `/ticket <ticket_id>`
- `/organism`
- `/help`
- `/top`
- `/meaning`
- `/why <symbol|isin>`
- `/alerts show`

Operator-Menues aus `modules/telegram_commands/ui.py`:

- `📈 Kaufen pruefen`
- `📉 Verkaufen pruefen`
- `🛡 Risiko reduzieren`
- `✅ Halten`
- `📋 Tickets`
- `📊 Status`
- `🧠 Top Ideen`
- `ℹ Hilfe`

## 8. Risikoregeln

Technisch sichtbare Risikoregeln im aktuellen Code:

- Budget-Grundlage: `hedgefund.budget_eur = 5000`
- `hedgefund.max_positions = 3`
- `hedgefund.max_risk_per_trade_pct = 1.0`
- `hedgefund.max_total_exposure_pct = 60`
- Buy-Signale sind nur operativ nutzbar, wenn Stop, Stop-Abstand, Risiko und Positionsgroesse belastbar vorliegen.
- Validierung dafuer sitzt in `modules/common/operator_signals.py`.
- `stop_method` ist normiert auf `structure`, `fallback`, `manual`.
- Struktur-Stop wird nur genutzt, wenn explizite Strukturanker plausibel vorliegen.
- Kein Buy-Signal ohne operative Pflichtfelder wird als vollwertiges, handlungsfaehiges Ticket behandelt.
- Marktstatus wird in `modules/virus_bridge/market_hours.py` geprueft.
- TR-Handelbarkeit wird statisch ueber `config/universe_tr_verified.json` geprueft.

## 9. Aktueller Qualitaetsstand

Im aktuellen Code-Stand vorhanden:

- operative Buy-/Sell-Validierung mit Pflichtfeldern
- informatives Handling fuer unvollstaendige Buy-Signale
- struktur-basierte Stop-Logik mit defensivem Fallback
- saubere Trennung `OPEN`, `PARTIALLY_CLOSED`, `CLOSED`
- gewichtete Exit-Auswertung ueber mehrere Exit-Dateien
- `exit_reason` mit Prioritaet Exit-Record vor Lifecycle vor markiertem Fallback
- `/execution` mit Kostenstatus, Warnlagen und echter Execution-Sicht
- `/organism` mit Kosten- und Aktivitaetsbezug
- `/tickets`, `/status`, `/portfolio`, `/help` in operatornaher deutscher Sprache

## 10. Offene Restbaustellen

Offene technische Grenzen, die im aktuellen Code weiterhin sichtbar sind:

- keine Broker- oder Depot-API zur automatischen Verifikation von Ausfuehrungen
- Struktur-Stops funktionieren nur mit expliziten Strukturankern im Proposal oder Quote, nicht aus eigener Candle-Historie
- offene PnL ist von belastbaren aktuellen Quotes aus `data/v2/candidates_*.json` abhaengig
- die Kostenreferenz in EUR bleibt eine explizite Annahme aus `organism_evaluation.eurusd_rate_assumption`
- Portfolio-Wahrheit kann im Modus `GEMISCHT` oder `TELEGRAM_AUSFUEHRUNGEN` nur so gut sein wie Snapshot und manuelle Ausfuehrungserfassung
- aeltere Detaildokumente unter `docs/` koennen textlich hinter dem aktiven Stand liegen
