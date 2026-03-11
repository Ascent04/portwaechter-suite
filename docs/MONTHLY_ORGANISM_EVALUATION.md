# Monthly Organism Evaluation

## Ziel

Die Monatsbewertung behandelt den CB Fund Desk wie ein laufendes System:

- Wie aktiv war der Desk?
- Wie gut waren echte Ausfuehrungen?
- Wie gross sind offene Risiken?
- Wie hoch war der API-Verbrauch?
- Rechtfertigt der Nutzen die laufenden Kosten?

Die Auswertung trifft keine automatische Betriebsentscheidung. Sie liefert nur eine transparente Monatsbewertung.

## Datenquellen

- `data/v2/recommendations_*.json`
- `data/virus_bridge/trade_candidates/`
- `data/virus_bridge/executions/`
- `data/virus_bridge/exits/`
- `data/virus_bridge/ticket_lifecycle/`
- `data/api_governor/usage_YYYYMMDD.jsonl`

## Kennzahlen

### Aktivitaet

- Scanner-Laeufe
- Gesamtzahl der Empfehlungen
- Kaufideen
- Verkaufssignale
- Risiko-reduzieren-Signale
- Halten-Signale
- Trade-Kandidaten
- Ausfuehrungen
- Teilverkaeufe
- Geschlossene Trades

### Performance

- Realisierter PnL
- Unrealisierter PnL
- Durchschnitt geschlossener Trades
- Trefferquote
- Beste und schwaechste Position

### Risiko

- Offene Positionen
- Teilweise geschlossene Positionen
- Offene Exponierung
- Groesste offene Position
- Groesstes offenes Risiko, wenn verfuegbar

### Betrieb

- Gesamtzahl der API-Calls
- Durchschnittliche Calls pro Tag
- Hoechste Last pro Minute
- Zahl gedrosselter und blockierter Minuten

### Wirtschaftlichkeit

Die Kostenannahme kommt aus `organism_evaluation` in `config.yaml`.

- `monthly_cost_usd`
- `eurusd_rate_assumption`

Daraus werden Monatskosten in EUR und PnL nach Kosten geschaetzt.

## Bewertungslogik

Moegliche Monatsurteile:

- `AUSBAUEN`
- `WEITER_FUEHREN`
- `GEDROSSELT_FUEHREN`
- `UEBERPRUEFEN`

Die Logik bleibt absichtlich einfach und transparent:

- wenig echte Ausfuehrungen + wenig nutzbare Signale -> `UEBERPRUEFEN`
- positive realisierte Performance + kontrollierte API-Nutzung -> `WEITER_FUEHREN` oder `AUSBAUEN`
- negative Performance nach Kosten oder API-Stress -> `GEDROSSELT_FUEHREN`

## Report-Datei

Der Monatsreport wird geschrieben nach:

- `data/organism/monthly/monthly_evaluation_YYYY_MM.json`

## Telegram

Der Command `/organism` erzeugt eine kompakte Monatszusammenfassung mit:

- Aktivitaet
- Performance
- Betrieb
- Kosten
- Monatsurteil
- Kurzfazit

## Grenzen

- Fehlende Live-Preise werden nicht kaschiert.
- Bei wenigen echten Ausfuehrungen ist die Aussagekraft gering.
- Kosten und EUR/USD-Annahme sind bewusst transparent und nur naeherungsweise.
