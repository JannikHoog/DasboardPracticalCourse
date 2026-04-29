# ERPsim Automation Bootstrap (Team CC)

This folder contains a safe starter setup for:

1. Reading data from ERPsim OData endpoints
2. Preparing decisions offline
3. (Removed) UI execution tools for SAP Fiori

For the long-term modular architecture (analytics, forecasting, external sources),
see `ARCHITECTURE.md` and `src/erpsim_platform/`.

## Safety defaults

- `execution_enabled=false` by default (execute mode blocked)
- `dry_run` is enabled by default
- no order-changing action is sent unless `confirm_live_actions=true`

## Setup

```bash
pip install -r requirements.txt
```

Optional (only for UI execution mode):

```bash
python -m playwright install chromium
```

## Configuration

1. Copy `automation/config.example.json` to `automation/config.json`
2. Fill in credentials and OData URLs
3. Keep `dry_run=true` for first runs

## Run

```bash
python automation/main.py --mode fetch
python automation/fetch_pipeline.py --interval-seconds 30
```

Run exactly one ingestion cycle:

```bash
python automation/fetch_pipeline.py --once
```

## Modes

- `fetch`: reads configured OData feeds and writes CSV snapshots
- `fetch_pipeline`: continuous read-only data ingestion loop (separate process)

## Notes

- Team is preset to `CC`
- This repo is operated in **reads-only** mode (OData fetch + offline decision support).
- Keep ingestion and analysis separate:
  - process 1: `automation/fetch_pipeline.py` (collect only)
  - process 2: dashboard / preparation / analysis (read snapshots only)
