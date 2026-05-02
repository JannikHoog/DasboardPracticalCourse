# ERPsim Session Handover (2026-04-27)

Purpose: Consolidated context file for other agents to continue work without rediscovery.

## 1) Project / Team Context

- Team: `JJ`
- Game mode: ERPsim Manufacturing Introduction (SAP Fiori UI, browser-based)
- Current working rule: read-only data collection first; no order execution by default.

## 2) Core Game Facts Confirmed Today

- Winner criterion: highest `Company_Valuation` at end of game.
- Hard rules:
  - No stock -> no sales.
  - Do not sell below cost (end inventory valued at cost).
  - Customer preferences stable within same game.
- Game structure:
  - 3 rounds, each 20 virtual days.
- Important business constraint:
  - Orders contain 4 products together (basket/co-purchase relevant).
- Price setting:
  - Product prices are not region-specific (important for analytics aggregation).

## 3) Files Created/Updated During Session

- `task.md`: project instructions (AI/data/agent strategy)
- `basic_rules.md`: persistent operating rules
- `spielregeln.md`: extracted and structured game rules
- `ARCHITECTURE.md`: platform architecture blueprint
- `requirements.txt`: dependencies
- `automation/*`: ingestion, dashboard, action tooling
- `src/erpsim_platform/*`: modular architecture skeleton

## 4) OData Access Facts

- OData base: `https://e05.bi.ucc.cit.tum.de/odata/935`
- Confirmed accessible directly in browser/API with entity URLs.
- Confirmed service collections (18):
  - `BOM_Changes`
  - `Carbon_Emissions`
  - `Company_Valuation`
  - `Current_Game_Rules`
  - `Current_Inventory`
  - `Current_Inventory_KPI`
  - `Current_Pricing_Conditions`
  - `Current_Suppliers_Prices`
  - `Financial_Postings`
  - `Independent_Requirements`
  - `Inventory`
  - `Market`
  - `Marketing_Expenses`
  - `Production`
  - `Production_Orders`
  - `Purchase_Orders`
  - `Sales`
  - `Stock_Transfers`

## 5) Data Structure Learned (Important Columns)

### Sales (`Sales`)

- Keys/timing: `SIM_ROUND`, `SIM_STEP`, `SIM_PERIOD`, `SIM_ELAPSED_STEPS`, `SIM_DATE`
- Dimensions: `AREA`, `MATERIAL_NUMBER`, `MATERIAL_DESCRIPTION`
- Measures: `QUANTITY`, `NET_PRICE`, `NET_VALUE`, `COST`

### Marketing (`Marketing_Expenses`)

- Timing: `SIM_ROUND`, `SIM_STEP`, `SIM_PERIOD`, `SIM_ELAPSED_STEPS`, `SIM_DATE`
- Dimensions: `AREA`, `MATERIAL_NUMBER`, `MATERIAL_DESCRIPTION`
- Measure: `AMOUNT`

### Market (`Market`)

- Timing: `SIM_ROUND`, `SIM_PERIOD`
- Dimensions: `AREA`, `MATERIAL_DESCRIPTION`, `SALES_ORGANIZATION` (notably `Market`)
- Measures: `AVERAGE_PRICE`, `QUANTITY`, `NET_VALUE`

### Pricing (`Current_Pricing_Conditions`)

- Dimensions: `MATERIAL_NUMBER`, `MATERIAL_DESCRIPTION`, `DISTRIBUTION_CHANNEL`
- Measure: `PRICE` (current list price)

### Company Value (`Company_Valuation`)

- Timing: `SIM_ROUND`, `SIM_STEP`, `SIM_ELAPSED_STEPS`
- Measures: `PROFIT`, `COMPANY_VALUATION`, cash/debt-related fields

## 6) Current Data Availability Status

- Snapshots exist in `automation/data/*.csv`.
- Live cache exists in `automation/data/live_cache/*.csv`.
- Verified at time of check: sales data currently from round 1 only (`SIM_ROUND = 1`, steps up to 19).
- No round 2/3 trade data persisted yet at check time.

## 7) Automation & Safety Status

- Config file: `automation/config.json`
- Safety flags:
  - `execution_enabled=false`
  - `dry_run=true`
  - `confirm_live_actions=false`
- Meaning: no live order actions should run unless explicitly enabled.

## 8) Dashboard Status (Current)

Primary dashboard file: `automation/dashboard.py`

Current focus simplified to:

- Our selling prices vs market prices
- Product-level comparison (aggregated across regions for pricing analysis)

Price concepts separated:

- `current_list_price` from `Current_Pricing_Conditions`
- `our_realized_price` from `Sales.NET_PRICE`
- `market_avg_price` from `Market.AVERAGE_PRICE`

Includes:

- Gap metrics (`list vs market`, `realized vs market`)
- Live fetch with configurable auto-refresh interval
- Stale/pause detection + cache fallback

## 9) Key Analytical Interpretations Agreed

- For pricing logic, aggregate across regions (since price decision is product-level, not region-level).
- For advertising logic, region-level analysis remains relevant (`AREA` in marketing/sales).
- Market competitor prices are not directly observable per competitor team.
  - A competitor price estimate can only be derived from market averages + our own price/volume.

## 10) Manual Action Tool Implemented

Removed in current workspace: UI/desktop automation tools (e.g. VK32 click helpers) are not used.

## 11) Commands Used Operationally

### Fetch OData snapshots

```bash
python automation/main.py --mode fetch --config automation/config.json
```

### Start dashboard

```bash
streamlit run automation/dashboard.py
```

### Start price click tool

```bash
# removed (reads-only policy)
```

## 12) Open Work / Recommended Next Steps for Agents

1. Keep existing `automation/data` snapshots immutable for this experiment.
2. Add a dedicated exporter that writes a merged "decision dataset" per step.
3. Validate price fields against UI truth (VK32) and OData truth (`Current_Pricing_Conditions`) each round.
4. For ad optimization, add lag sensitivity (0/1/2-step) and confidence bands.
5. Once approved, implement controlled live executors for:
  - procurement action
  - advertisement update
  - product price update
   with explicit pre-submit confirmation.

## 13) Security / Handling Notes

- Do not store credentials in shared files.
- Keep secrets only in local runtime config that is not shared externally.
- Preserve read-only defaults unless user explicitly requests execution.

