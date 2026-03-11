# FULL_TEST_STATUS

Stand: 2026-03-11
Repo: `/opt/portwaechter`

## 1. Volltest

Ausgefuehrt:

```bash
cd /opt/portwaechter
./.venv/bin/python -m pytest -q
```

Finales Ergebnis:

- `270 passed in 11.87s`

## 2. Kurzverlauf

Der erste Volltestlauf war fast gruen, aber nicht komplett:

- `2 failed, 265 passed`

Ursache:

- zwei veraltete Text-Assertions gegen den neuen `/organism`-Warnstil
- keine fachliche Logikabweichung im Desk-Kern

Nachgezogen wurden:

- `tests/test_dry_run_scenarios.py`
- `tests/test_realbetrieb_readiness.py`

Danach war der komplette Recheck gruen.

## 3. Was damit testseitig bestaetigt ist

- aktiver Signalpfad von Proposal bis TradeCandidate
- Risk Eval, Stop-Loss und Ticket-Reife
- Telegram-Operatortexte und Warnlagen
- manueller Entry-/Exit-Workflow
- Partial Exit, Full Exit, Closed-Trade-Auswertung
- `/execution`, `/portfolio`, `/organism`, `/tickets`
- Runtime-Bootstrap fuer leeren Erstbetrieb
- Demo-/Seed-Bootstrap
- Telegram-Abschlussmeldung inklusive Dedupe- und Fehlerpfad

## 4. Ehrliche Einordnung

Technisch:

- Die Suite ist im aktuellen Code-Stand voll gruen.

Operativ:

- Der aktive Desk-Pfad wirkt testseitig stabil und konsistent.

Wirtschaftlich / Realbetrieb:

- Der Volltest ersetzt keinen echten Feldbetrieb.
- Im echten Produktivdatenpfad fehlen weiterhin reale `execution_*.json`- und `exit_*.json`-Daten.

## 5. Offene Restgrenze

- Gruene Tests bestaetigen den Code-Stand.
- Sie bestaetigen noch nicht den ersten echten manuellen Trade im Live-Betrieb.
