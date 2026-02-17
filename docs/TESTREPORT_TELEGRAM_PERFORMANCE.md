# Telegram Test Report - Performance Weekly (E: stat. relevant only)

## Metadaten
- Datum/Zeit: 2026-02-18T00:24:18+01:00
- Commit: `2bc0231`
- System: `/opt/portwaechter`
- Python: `/opt/portwaechter/.venv/bin/python`
- Feature: `modules/performance/telegram_reporting.py`

## Konfiguration (Thresholds)
Aus `config/config.yaml`:
- `performance.telegram_enabled: true`
- `performance.telegram_min_n: 30`
- `performance.telegram_min_n_regime: 20`
- `performance.telegram_min_n_bucket: 15`

## Testziel
- Nur senden, wenn statistisch relevant.
- Kein Versand bei Mini-Stichprobe.
- Kein Crash bei fehlenden Feldern.
- Telegram-Text mit Expectancy und Längenlimit.

## TC-01 NEGATIV: n < threshold
### Steps
- `python -m modules.performance.main report-weekly`

### Ergebnis
- Output: `performance_not_statistically_relevant`
- Weekly report geschrieben: `data/performance/reports/weekly_2026W08.json`
- `by_horizon` im Report: `n=0` fuer `1d/3d/5d`

### Verdict
- **PASS** (kein Versand bei kleiner Stichprobe)

## TC-02 POSITIV (deterministisch, kein Versand): Guard + Formatter
### Steps
- Synthetischer Report via Python-Block gegen `is_statistically_relevant` und `build_telegram_summary`.

### Ergebnis
- `is_statistically_relevant = True`
- `len(text) = 333` (< 2500)
- Summary enthaelt `Expectancy` und Horizont-Bloecke.

### Verdict
- **PASS**

## TC-03 POSITIV (realer Versand)
### Steps
- `send_if_relevant(report, cfg)` mit relevantem synthetischem Report.

### Ergebnis
- Output: `performance_telegram_sent`
- Kein Crash.
- Hinweis: Message-ID konnte nicht ueber `getUpdates` ausgelesen werden (wahrsch. Polling/Webhook-Kontext).

### Verdict
- **PASS**

## TC-04 ROBUST: expectancy=None
### Steps
- `is_statistically_relevant({'by_horizon': {'3d': {'n': 999, 'expectancy': None}}}, cfg)`

### Ergebnis
- `False`

### Verdict
- **PASS**

## Pytest Pflichtlauf
- Command: `pytest -q`
- Ergebnis: `39 passed`

## Gesamtbewertung
- Guarded Telegram Reporting verhaelt sich wie gefordert:
  - Kein Versand bei nicht relevanten Daten.
  - Versand bei relevanten Daten.
  - Deterministischer Formatter unter Laengenlimit.
  - Robuster Umgang mit fehlender `expectancy`.
