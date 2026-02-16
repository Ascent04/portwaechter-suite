# Security

- Das System ist strikt read-only und führt keine Trades aus.
- Es werden keine Secrets im Repository gespeichert.
- Telegram-Credentials werden ausschließlich über ENV (`TG_BOT_TOKEN`, `TG_CHAT_ID`) gelesen.
- Laufzeitdaten (PDFs, JSON/JSONL, Reports) liegen unter `data/` und sind gitignored.
- Audit-Logs werden append-only in `data/audit/*.jsonl` geschrieben.
