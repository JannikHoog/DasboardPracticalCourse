## ERPsim — Workspace

Dieser Workspace ist bewusst so organisiert, dass wir **Spielwissen + Datensnapshots behalten**, aber Analyse-/Dashboard-Experimente jederzeit **neu starten** können.

### Was unbedingt behalten wird (Wissen)

- `spielregeln.md`: konsolidierte Spielregeln
- `session_handover_2026-04-27.md`: gesammelte ERPsim-Fakten + OData-Views + Learnings
- `task.md` und `basic_rules.md`: Arbeitsprinzipien / Vorgehen
- `Docs/` und `Lectures/`: Kursmaterial
- **`marketInformation.md`**: Referenz aus dem Kursmaterial **Preset 3 – Manufacturing Sustainability** (DC-Segmente, Regionen, Lieferanten, Logistik-Kosten und CO₂e, Fixkosten, Kapazität). Dient als **abgleichbare Kurzfassung** neben den PDFs; Tabellen sind absichtlich klein gehalten, damit ihr sie schnell anpassen könnt.
- **`company_valuation_logic.md`**: Siegbedingung (**höchste `COMPANY_VALUATION` am Ende**), OData-Felder von `Company_Valuation`, Wirkungsketten Entscheidung → Bilanz/P&L → Bewertung, Heuristik-Tabelle für Agents, Monitoring-Hinweise. **Keine erfundene Bewertungsformel** — exakte Gewichtung ggf. aus Kurs-PDF ergänzen; Live-Daten haben Vorrang.

#### Wofür `marketInformation.md` genutzt wird

- **Menschen im Team**: gleiche Begriffe (DC 10/12/14, Regionen, SKU-Muster, Kostenannahmen) beim Spielen und beim Lesen des Dashboards.
- **Heuristiken im Code** (`workbench/`): Plausibilitätsprüfung und Erklärung von Empfehlungen (z. B. Werbung vs. Preis, Transfer vs. Direktlieferung), wenn Live-Werte aus `current_game_rules` / OData abweichen.
- **Zukünftige Agents (KI)**: Vor Analyse, Dashboard-Texten oder neuen Regeln **`marketInformation.md`**, **`company_valuation_logic.md`** und die **PDFs in `Docs/`** einbeziehen. Reihenfolge: (1) Tabellen in `marketInformation.md` / Bewertungslogik lesen, (2) bei Konflikten oder fehlenden Details die **Original-PDF** nachziehen, (3) **Live-Daten** aus OData / Snapshots haben Vorrang gegenüber veralteten Notizen in diesen Dateien.

### Daten (Snapshots)

- `automation/data/*.csv`: zeitgestempelte OData-Snapshots (append-only)
- `automation/data/live_cache/`: abgeleitete Live-Caches (nicht als “Quelle der Wahrheit” gedacht)

### “Neu anfangen” (ab jetzt)

- Neuer Code für Analysen/Dashboards kommt nach `workbench/`.
- Der bisherige Streamlit-Prototyp in `automation/dashboard.py` gilt als **Legacy/Experiment** und ist nicht die Basis für die nächste Iteration.

### Quickstart (Read-only OData Snapshot)

1. Dependencies installieren:

```bash
pip install -r requirements.txt
```

2. Config anlegen (ohne Secrets zu committen):
   - `automation/config.example.json` nach `automation/config.json` kopieren
   - Credentials nur lokal eintragen

3. Snapshots ziehen:

```bash
python automation/main.py --mode fetch --config automation/config.json
```

