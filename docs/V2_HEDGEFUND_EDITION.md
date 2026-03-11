# PortWächter V2 Hedge-Fund Edition

## Architektur
- `modules/v2/universe/*` baut Holdings- und Scanner-Universe.
- `modules/v2/marketdata/*` nutzt Twelve Data als Primärquelle und Stooq/Bestandsdaten als Fallback.
- `modules/v2/scanner/*` bewertet Momentum, Volume, News und Relative Strength.
- `modules/v2/scoring/*` ergänzt Portfolio-Priorität, Opportunity- und Defense-Scoring.
- `modules/v2/recommendations/*` klassifiziert in `WATCH`, `ACTION`, `DEFENSE`, `IGNORE` und rendert Telegram-Texte.
- `modules/v2/telegram/notifier.py` nutzt die bestehende Telegram-Infrastruktur mit Dedupe, Cooldown und Tageslimits.
- `modules/v2/main.py` orchestriert den V2-Lauf ohne Orders oder Broker-Calls.

## Datenfluss
1. Config laden über `modules/v2/config.py`.
2. Aktuellen Portfolio-Snapshot aus `data/snapshots` lesen.
3. Scanner-Universe aus `config/scanner_universe_v2.json` plus optional `data/watchlist/watchlist.json` laden.
4. Quotes via Twelve Data holen, bei Fehlern auf vorhandene Marketdata-/Stooq-Logik zurückfallen.
5. News aus `data/news/top_opportunities_*.json` und `data/news/items_translated_*.jsonl` laden.
6. Kandidaten scannen, scoren, klassifizieren, persistieren und selektiv per Telegram verschicken.

## Universe
- Holdings liefern `isin`, `name`, `market_value_eur`, `weight_pct`, `symbol`, `group=holding`.
- Scanner-Universe liefert `symbol`, optional `isin`, `name`, `country`, `sector`, `group=scanner`.
- Beim Merge gewinnt `group=holding`, damit bestehende Positionen defense-aware bleiben.

## Scores
- Momentum: `0..3` auf Basis von `percent_change`.
- Volume: `0..2` gegen vorhandene Rolling-Baseline.
- News: `0..3` mit Fokus auf IR, Regulatory, Earnings, Guidance, Acquisition, Warning, Outlook.
- Relative Strength: `0..2` als Percentile-Ranking innerhalb des aktuellen Runs.
- Opportunity Score: Basissumme plus Regime-, Expectancy- und Portfolio-Prioritäts-Adjustments.
- Defense Score: negativer Move, Gewicht, negative News und `risk_off`-Regime.

## Telegram Kategorien
- `WATCH`: Setup beobachten, keine Handlungsempfehlung.
- `ACTION`: Priorisierte Chance, aber explizit ohne Trade- oder Order-Auslösung.
- `DEFENSE`: Risiko-Hinweis für bestehende Positionen oder harte negative Setups.
- Limits pro Tag: `WATCH 10`, `ACTION 3`, `DEFENSE 5`.

## systemd Setup
- Service: `systemd/portwaechter-v2.service`
- Timer: `systemd/portwaechter-v2.timer`
- Working Directory: `/opt/portwaechter`
- User: `ascent`
- Environment File: `/etc/portwaechter/portwaechter.env`

## ENV Keys
- `TWELVEDATA_API_KEY` für Intraday-Quotes.
- `TG_BOT_TOKEN` und `TG_CHAT_ID` über bestehende Telegram-Konfiguration.

## Fallback Verhalten
- Primär: Twelve Data `quote` Endpoint.
- Sekundär: zuletzt vorhandene `data/marketdata/quotes_*.jsonl`.
- Tertiär: bestehende Stooq-Logik via `modules.marketdata_watcher.adapter_http`.
- Bei Fehlschlägen bleibt der Lauf stabil; Quotes werden mit `status=error` und `provider=none` markiert.

## Guardrails
- Keine Auto-Trades.
- Keine Orders.
- Keine Secrets im Repo.
- Keine Heavy Dependencies.
- Fehler in Marketdata oder Telegram dürfen den V2-Lauf nicht abbrechen.
