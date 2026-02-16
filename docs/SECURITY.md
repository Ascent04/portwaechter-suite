# Security

- Das System ist strikt read-only und führt keine Trades aus.
- Alle Modi (1-4) erzeugen nur Monitoring-, Signal- oder Reporting-Ausgaben.
- Es werden keine Secrets im Repository gespeichert.
- Telegram-Credentials werden ausschließlich über ENV (`TG_BOT_TOKEN`, `TG_CHAT_ID`) gelesen.
- Laufzeitdaten (PDFs, JSON/JSONL, Reports, State) liegen unter `data/` und sind gitignored.
- Audit-Logs werden append-only in `data/audit/*.jsonl` geschrieben.
