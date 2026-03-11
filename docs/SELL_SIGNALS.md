## Sell Signals

Die Sell-Logik des CB Fund Desk unterscheidet fuer bestehende Positionen zwischen `HALTEN`, `RISIKO REDUZIEREN` und `VERKAUFEN PRUEFEN`.

### HALTEN

Eine Holding wird als `HALTEN` eingestuft, wenn:

- kein deutlicher negativer Preisimpuls vorliegt
- die Nachrichtenlage nicht belastend ist
- das Marktumfeld die Position nicht klar unter Druck setzt
- kein erhoehtes Klumpenrisiko sichtbar wird

### RISIKO REDUZIEREN

Eine Holding wird als `RISIKO REDUZIEREN` eingestuft, wenn:

- das Positionsgewicht hoch ist
- die Marktlage defensiv oder unsicher ist
- das Signal kippt, aber noch kein klarer Exit-Fall vorliegt
- leichte negative Nachrichten oder Konzentrationsrisiken sichtbar sind

### VERKAUFEN PRUEFEN

Eine Holding wird als `VERKAUFEN PRUEFEN` eingestuft, wenn:

- der Preisimpuls deutlich negativ ist
- belastende Nachrichten hinzukommen
- hohes Gewicht und negatives Signal zusammenfallen
- die Schwaeche klar ueber normales Rauschen hinausgeht

### Einflussfaktoren

- Depotgewicht: hohe Gewichte erhoehen die Relevanz negativer Signale
- Nachrichtenlage: Gewinnwarnungen, Downgrades, regulatorische Risiken und Kapitalmassnahmen zaehlen negativ
- Marktlage: defensive Phasen beguenstigen eher Risikoreduktion
- Klumpenrisiko: wirkt nur als Verstaerker, nie allein

### Grenzen

- Es gibt keine Auto-Verkaeufe.
- Die Logik bleibt bewusst robust und einfach.
- Ohne Gewicht, Sektor oder Theme bleibt die Bewertung neutraler.
