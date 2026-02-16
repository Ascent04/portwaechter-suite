# portwaechter-suite
Read-only Aktienportfolio-System: TR-Depotauszug (PDF) -> Portfolio-Analyse, Live-Kurse (best effort), News & Chancen-Tracking. Kein Trading.

## Setup
1. Python-Umgebung erstellen und Abhängigkeiten installieren (`pdfminer.six`, `feedparser`, `PyYAML`, `pytest`).
2. Konfiguration unter `config/config.yaml` prüfen.
3. Laufzeitverzeichnisse sicherstellen:
   - `data/inbox`
   - `data/raw`
   - `data/snapshots`
   - `data/reports`
   - `data/audit`
   - `data/marketdata`
   - `data/news`

## Environment
Telegram wird nur genutzt, wenn in der Config aktiviert und diese ENV-Variablen gesetzt sind:
- `TG_BOT_TOKEN`
- `TG_CHAT_ID`

## Run-Kommandos
- Portfolio ingest:
  - `python -m modules.portfolio_ingest.main run`
- Marketdata watcher:
  - `python -m modules.marketdata_watcher.main run`
- News tracker:
  - `python -m modules.news_tracker.main run`

## systemd
Unit-Dateien liegen unter `systemd/`.

1. Units installieren:
   - `sudo cp systemd/portwaechter-portfolio.service /etc/systemd/system/`
   - `sudo cp systemd/portwaechter-portfolio.path /etc/systemd/system/`
   - `sudo cp systemd/portwaechter-marketdata.service /etc/systemd/system/`
   - `sudo cp systemd/portwaechter-marketdata.timer /etc/systemd/system/`
   - `sudo cp systemd/portwaechter-news.service /etc/systemd/system/`
   - `sudo cp systemd/portwaechter-news.timer /etc/systemd/system/`

2. Aktivieren und starten:
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable --now portwaechter-portfolio.path`
   - `sudo systemctl enable --now portwaechter-marketdata.timer`
   - `sudo systemctl enable --now portwaechter-news.timer`

Hinweis: `portwaechter-portfolio.path` nutzt `PathExistsGlob=/opt/portwaechter/data/inbox/*.pdf` (inotify-basiert).
