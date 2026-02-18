# Telegram Commands

## Sicherheit
- Nur Chat-IDs aus `telegram_commands.allowed_chat_ids_env` werden akzeptiert.
- Standard: `TG_CHAT_ID` aus `/etc/portwaechter/portwaechter.env`.
- Alle empfangenen Updates werden in `data/telegram/inbox_YYYYMMDD.jsonl` protokolliert.

## Aktivieren
```bash
sudo cp systemd/portwaechter-commands.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now portwaechter-commands.timer
systemctl status portwaechter-commands.timer --no-pager
```

Optional Tactical Warning:
```bash
sudo cp systemd/portwaechter-warnings.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now portwaechter-warnings.timer
```

## Manueller Test
```bash
cd /opt/portwaechter
/opt/portwaechter/.venv/bin/python -m modules.telegram_commands.poller run
/opt/portwaechter/.venv/bin/python -m modules.performance.warnings run
```

## Befehle
- `/status`
- `/alerts`
- `/alerts quiet`
- `/alerts balanced`
- `/alerts active`
- `/help`

## Dauerhafte Buttons
- Reply-Keyboard ist aktiv über `telegram_commands.keyboard.enabled=true`.
- Buttons bleiben sichtbar mit `persistent=true`.
- Layout wird über `telegram_commands.keyboard.rows` gesteuert.

## Beispielantworten
- Status: `overall=ok`, `marketdata=...`, `briefing_latest=ok|missing`
- Alerts: aktuelles Profil + Kernschwellen
- Tactical Warning: `⚠ Tactical Warning: 3d Expectancy < 0 ...`
