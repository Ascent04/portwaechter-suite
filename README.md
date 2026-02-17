# portwaechter-suite
Read-only Aktienportfolio-System: TR-Depotauszug (PDF) -> Snapshot/Analyse/Report, Live-Kurse (best effort), News/Chancen-Ranking. Kein Trading.

## Setup
1. Python-Umgebung erstellen und Abhängigkeiten installieren:
   - `python -m venv .venv`
   - `. .venv/bin/activate`
   - `pip install -r requirements.txt`
2. Konfiguration unter `config/config.yaml` prüfen.
3. Laufzeitverzeichnisse sicherstellen:
   - `data/inbox`, `data/raw`, `data/snapshots`, `data/reports`
   - `data/audit`, `data/marketdata`, `data/news`, `data/signals`, `data/radar`, `data/state`

## Environment
Telegram nur via ENV:
- `TG_BOT_TOKEN`
- `TG_CHAT_ID`

## Betriebsmodi
`app.mode` in `config/config.yaml` steuert den Ablauf:
1. `mode=1`: Portfolio ingest + Marketdata watcher + News tracker (holdings-basiert)
2. `mode=2`: Mode 1 + Signal Engine
3. `mode=3`: Mode 1 + Optimizer Engine (Vorschläge, keine Trades)
4. `mode=4`: Radar (RSS-Universe + Ranking + Telegram)

## Run-Kommandos
- Zentraler Modus-Runner:
  - `python -m modules.main run`
- Einzel-Runner bleiben verfügbar:
  - `python -m modules.portfolio_ingest.main run`
  - `python -m modules.marketdata_watcher.main run`
  - `python -m modules.news_tracker.main run`

## Dedupe/Cooldown
Telegram-Dedupe + Cooldown nutzen `data/state/notify_state.json`.
Cooldown wird über `notify.telegram.cooldown_min` gesteuert.

## systemd
Unit-Dateien liegen unter `systemd/`.

Für Mode 1 typischer Betrieb:
1. `portwaechter-portfolio.path` (PDF Trigger)
2. `portwaechter-marketdata.timer` (5 min)
3. `portwaechter-news.timer` (15 min)

Für Mode 2-4 optional einen eigenen Service/Timer auf `python -m modules.main run` anlegen.

## Morning Briefing
- Runner: `python -m modules.briefing.morning run`
- systemd:
  - `systemd/portwaechter-briefing.service`
  - `systemd/portwaechter-briefing.timer` (`OnCalendar=*-*-* 08:30:00 Europe/Berlin`, `Persistent=true`)

## D+ Performance Engine
Die Performance-Engine bewertet automatisch alle erzeugten Signale/Setups
und berechnet Forward Returns (1d/3d/5d) sowie woechentliche KPI-Reports.

### Datenablage
- Events:
  - `data/performance/events_YYYYMMDD.jsonl`
- Outcomes:
  - `data/performance/outcomes_YYYYMMDD.jsonl`
- Weekly Reports:
  - `data/performance/reports/weekly_YYYYWww.json`

### CLI
- Evaluation:
  - `python -m modules.performance.main eval --days 30`
- Weekly Report:
  - `python -m modules.performance.main report-weekly`
- Standardlauf:
  - `python -m modules.performance.main run`

### systemd (optional)
- Service:
  - `systemd/portwaechter-performance.service`
- Timer:
  - `systemd/portwaechter-performance.timer`

Installieren:
1. `sudo cp systemd/portwaechter-performance.* /etc/systemd/system/`
2. `sudo systemctl daemon-reload`
3. `sudo systemctl enable --now portwaechter-performance.timer`

Status pruefen:
- `systemctl status portwaechter-performance.timer`
