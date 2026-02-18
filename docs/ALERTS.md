# Alerts Steuerung

## Telegram Commands
- `/status`
- `/status verbose`
- `/alerts show`
- `/alerts set active|normal|quiet|off`
- `/alerts thresholds market <threshold_pct> <min_delta_pct>`
- `/alerts thresholds market off`
- `/testalert market|watch|performance`

## Profile
- `active`: Market + Watch + Performance Warn aktiv, niedrigere Floors.
- `normal`: Standardbetrieb mit moderaten Floors/Cooldowns.
- `quiet`: Strenger Betrieb, Market nur bei `threshold_cross`, Watch nur wichtige Signale.
- `off`: Alle Alerts aus (Status-Kommandos bleiben nutzbar).

## Soll-Format (Marketdata Telegram)
- Eine Zeile pro Instrument:
  - `PortWächter Marketdata: <NAME> (<ISIN>) <CURRENT>% | Δ=<DELTA>% | Trigger: <TRIGGER> | Gruppe: <GROUP>`
- Beispiel:
  - `PortWächter Marketdata: BASF SE (DE000BASF111) +1.24% | Δ=+0.83% | Trigger: delta+direction_change | Gruppe: holdings`

## Default Thresholds Je Profil
- `active`
  - `holdings`: `min_delta_pct=0.5`, `min_direction_pct=0.7`, `threshold_pct=2.6`
  - `radar`: `min_delta_pct=1.0`, `min_direction_pct=1.2`, `threshold_pct=3.6`
  - `threshold_cross_only=false`, `max_per_day=14`
- `normal`
  - `holdings`: `min_delta_pct=0.7`, `min_direction_pct=0.9`, `threshold_pct=3.0`
  - `radar`: `min_delta_pct=1.2`, `min_direction_pct=1.5`, `threshold_pct=4.0`
  - `threshold_cross_only=false`, `max_per_day=10`
- `quiet`
  - `holdings`: `min_delta_pct=1.0`, `min_direction_pct=1.2`, `threshold_pct=3.8`
  - `radar`: `min_delta_pct=1.5`, `min_direction_pct=1.8`, `threshold_pct=4.8`
  - `threshold_cross_only=true`, `max_per_day=4`
- `off`
  - `marketdata_alerts.enabled=false`
  - `watch_alerts.enabled=false`
  - `tactical_warnings.enabled=false`

## Beispiele
```text
/alerts set active
/alerts show
/alerts thresholds market 1.0 0.5
/status verbose
/testalert market
```

## Runtime-Overrides
- Datei: `data/runtime_overrides.json`
- Wird atomar geschrieben (tmp + replace).
- Überschreibt `config/config.yaml` nur zur Laufzeit (nicht in Git).

## Debugging
- Marketdata Summary pro Run in Journal:
  - `evaluated=N sent=S suppressed=K reasons={...}`
- Optional detailliert je ISIN:
  - `DEBUG_ALERTS=1` oder `debug.alerts=true` in Config.
