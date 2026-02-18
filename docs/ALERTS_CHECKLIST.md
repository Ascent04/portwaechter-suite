# Alerts Checklist

## 1) Tests
```bash
cd /opt/portwaechter
/opt/portwaechter/.venv/bin/python -m pytest -q
```

## 2) Timer/Service Status
```bash
systemctl status portwaechter-marketdata.timer --no-pager
systemctl status portwaechter-watchalerts.timer --no-pager
systemctl list-timers | grep -E 'portwaechter-(marketdata|watchalerts)'
```

## 3) Manuelle Trigger
```bash
cd /opt/portwaechter
/opt/portwaechter/.venv/bin/python -m modules.marketdata_watcher.main run
/opt/portwaechter/.venv/bin/python -m modules.watch_alerts.main run
```

## 4) Journals (sent vs suppressed)
```bash
journalctl -u portwaechter-marketdata.service -n 120 --no-pager
journalctl -u portwaechter-watchalerts.service -n 120 --no-pager
```

## 5) Micro-Alert Filter Check (Balanced)
- Holdings: keine Alerts unter `0.7%`.
- Radar: keine Alerts unter `1.2%`.
- Prüfen über Trigger-Log der letzten 2 Stunden:
```bash
journalctl -u portwaechter-marketdata.service --since \"2 hours ago\" --no-pager | grep -E \"Trigger|PortWächter Marketdata\"
```
- State-Updates prüfen:
```bash
cat /opt/portwaechter/data/alerts/state.json | head -n 120
```

## 6) Duplicate Guard Check
- Beobachte Telegram 2 Stunden.
- Es darf keine identische Nachricht pro ISIN mit identischem Wert erneut kommen.
- Watch-Messages in Quiet Hours (22:00-07:00 Europe/Berlin) dürfen nicht erscheinen.
