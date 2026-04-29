## ERPsim (Team CC) — Workspace

Dieser Workspace ist bewusst so organisiert, dass wir **Spielwissen + Datensnapshots behalten**, aber Analyse-/Dashboard-Experimente jederzeit **neu starten** können.

### Was unbedingt behalten wird (Wissen)

- `spielregeln.md`: konsolidierte Spielregeln
- `session_handover_2026-04-27.md`: gesammelte ERPsim-Fakten + OData-Views + Learnings
- `task.md` und `basic_rules.md`: Arbeitsprinzipien / Vorgehen
- `Docs/` und `Lectures/`: Kursmaterial

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

