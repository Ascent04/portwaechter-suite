# DEMO_ONLY

Dieser Bereich ist nur fuer lokale Trockenlaeufe und Erstinbetriebnahme gedacht.
Er gehoert nicht zur echten Produktivdatenlage unter `/opt/portwaechter/data`.

Zweck:
- erste Proposal-Datei ohne Live-Scanner pruefen
- erste Execution-/Exit-Datei fuer `/execution` und `/organism` bereitstellen
- erste Portfolio-/Desk-Auswertung ohne echte Handelsdaten testen

Bootstrapping:
```bash
cd /opt/portwaechter
./.venv/bin/python scripts/bootstrap_demo_desk.py --clean
```

Standard-Ziel:
- `/opt/portwaechter/testdata/demo_desk_runtime`

Wichtige Regel:
- Demo-Root getrennt halten
- keine Demo-Dateien in den echten Laufzeitpfad `/opt/portwaechter/data` kopieren
- alle Demo-Dateien tragen `demo_label = DEMO_ONLY`

Nach dem Lauf liegen dort u. a.:
- `data/integration/signal_proposals/...`
- `data/virus_bridge/executions/...`
- `data/virus_bridge/exits/...`
- `data/virus_bridge/ticket_lifecycle/...`
- `data/snapshots/...`
- `data/virus_bridge/performance/...`
- `data/organism/monthly/...`
- `output/demo_summary.txt`
