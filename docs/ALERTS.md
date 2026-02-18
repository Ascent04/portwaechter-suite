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
