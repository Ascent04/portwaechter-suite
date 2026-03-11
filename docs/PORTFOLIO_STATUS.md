Portfolio Status V1

Ziel
- `/portfolio` zeigt den aktuell bekannten Bestandsstand des Desk.
- Der Command behauptet keinen Live-Brokerstand, wenn nur Snapshot- oder manuell gepflegte Daten vorliegen.

Datenquellen
- Bestaetigter Bestand: `data/snapshots/portfolio_*.json`
- Fallback-Snapshot: `data/portfolio/*.json`
- Manuelle Ausfuehrungen: `data/virus_bridge/executions/YYYYMMDD/execution_*.json`
- Offene Restgroessen: `data/virus_bridge/ticket_state.json`
- Mark-to-Market fuer manuelle Desk-Positionen: bestehende Virus-Bridge-Performance-Logik

Modell
- `raw_source_snapshot`: letzter bestaetigter Snapshot, falls vorhanden
- `derived portfolio snapshot`: abgeleiteter operativer Stand fuer Telegram

Wichtige Felder
- `snapshot_id`
- `created_at`
- `source_type`
- `source_details`
- `freshness_status`
- `confidence_status`
- `positions_count`
- `gross_value_eur`
- `cash_eur`
- `free_budget_eur`
- `notes`
- `positions[]`

Quellenlogik
- `DEPOTAUSZUG`: bestaetigter Snapshot ohne neuere manuelle Ausfuehrungen
- `GEMISCHT`: bestaetigter Snapshot plus neuere manuelle Desk-Ausfuehrungen
- `TELEGRAM_AUSFUEHRUNGEN`: kein Snapshot, nur manuell gepflegte Desk-Positionen
- `UNBEKANNT`: kein belastbarer Stand vorhanden

Frische
- `AKTUELL`: bestaetigter Snapshot ist frisch
- `TEILWEISE_AKTUELL`: gemischter oder rein manueller Stand, operativ noch brauchbar
- `VERALTET`: letzter belastbarer Stand ist alt oder unvollstaendig

Datenqualitaet
- `HOCH`: frischer, bestaetigter Snapshot
- `MITTEL`: gemischte oder manuelle, aber noch brauchbare Datenlage
- `NIEDRIG`: veraltete oder unvollstaendige Daten

Wichtige Guardrails
- Kein Fantasie-Cash
- Kein behaupteter Live-Stand
- `free_budget_eur` nur, wenn aus Cash oder aus dem taktischen Desk-Budget ableitbar
- Konflikte zwischen Snapshot und manuellen Events werden im Hinweis offen benannt
