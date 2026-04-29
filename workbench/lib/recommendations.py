from __future__ import annotations

from dataclasses import dataclass
import math
import re

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PriceSuggestion:
    distribution_channel: str
    material_number: str
    material_description: str
    current_price: float
    market_avg_price: float | None
    inventory_units: float | None
    recent_units_sold_per_step: float | None
    suggested_price: float
    reason: str


@dataclass(frozen=True)
class ProductionSuggestion:
    material_number: str
    material_description: str
    inventory_units: float
    demand_units_per_day_est: float
    coverage_days: float
    suggested_batch_units: int
    reason: str


@dataclass(frozen=True)
class ProcurementSuggestion:
    material_number: str
    material_description: str
    unit: str
    inventory: float
    target: float
    suggested_purchase_qty: float
    reason: str


@dataclass(frozen=True)
class ActionTip:
    priority: int
    category: str
    material_number: str | None
    title: str
    suggested_action: str
    rationale: str


@dataclass(frozen=True)
class InvestmentSuggestion:
    investment: str
    cost_eur: float
    estimated_saving_eur_per_5days: float | None
    est_payback_days: float | None
    recommendation: str


@dataclass(frozen=True)
class TransferSuggestion:
    material_number: str
    material_description: str
    from_storage_location: str
    to_storage_location: str
    to_area: str
    estimated_qty: float
    transfer_cost_eur: float
    co2_penalty_eur: float
    expected_margin_eur_per_unit: float
    expected_net_gain_eur: float
    urgency: str
    rationale: str


@dataclass(frozen=True)
class AdvertisingSuggestion:
    material_number: str
    material_description: str
    area: str
    recent_market_qty: float
    recent_our_qty: float
    recent_share_pct: float
    target_share_pct: float
    current_ad_spend_eur: float
    suggested_ad_spend_eur: float
    priority: str
    rationale: str


def _to_step_id(df: pd.DataFrame) -> pd.Series:
    if "SIM_ELAPSED_STEPS" in df.columns:
        return pd.to_numeric(df["SIM_ELAPSED_STEPS"], errors="coerce").fillna(0).astype(int)
    rnd = pd.to_numeric(df.get("SIM_ROUND", 0), errors="coerce").fillna(0).astype(int)
    step = pd.to_numeric(df.get("SIM_STEP", 0), errors="coerce").fillna(0).astype(int)
    return rnd * 100 + step


def _safe_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def _market_avg_price(market: pd.DataFrame) -> pd.DataFrame:
    if market.empty:
        return pd.DataFrame(columns=["DISTRIBUTION_CHANNEL", "MATERIAL_DESCRIPTION", "market_avg_price"])
    m = _safe_numeric(market, ["AVERAGE_PRICE", "QUANTITY"])

    def _weighted(g: pd.DataFrame) -> float:
        w = g["QUANTITY"].clip(lower=0).fillna(0)
        if float(w.sum()) <= 0:
            return float(g["AVERAGE_PRICE"].mean())
        return float(np.average(g["AVERAGE_PRICE"], weights=w))

    return (
        m.groupby(["DISTRIBUTION_CHANNEL", "MATERIAL_DESCRIPTION"], dropna=False)
        .apply(lambda g: pd.Series({"market_avg_price": _weighted(g)}))
        .reset_index()
    )


def _recent_sales_rate(sales: pd.DataFrame, lookback_steps: int = 3) -> pd.DataFrame:
    if sales.empty:
        return pd.DataFrame(columns=["DISTRIBUTION_CHANNEL", "MATERIAL_DESCRIPTION", "recent_units_sold_per_step"])
    s = _safe_numeric(sales, ["QUANTITY"])
    s["step_id"] = _to_step_id(s)
    max_step = int(s["step_id"].max())
    window = s[s["step_id"] >= (max_step - lookback_steps + 1)]
    agg = (
        window.groupby(["DISTRIBUTION_CHANNEL", "MATERIAL_DESCRIPTION"], dropna=False)["QUANTITY"]
        .sum()
        .reset_index()
    )
    agg["recent_units_sold_per_step"] = agg["QUANTITY"] / max(lookback_steps, 1)
    return agg.drop(columns=["QUANTITY"])


def build_price_suggestions(
    *,
    sales: pd.DataFrame,
    market: pd.DataFrame,
    pricing: pd.DataFrame,
    inventory: pd.DataFrame,
    price_step_eur: float,
    max_steps: int,
) -> list[PriceSuggestion]:
    if pricing.empty:
        return []

    p = _safe_numeric(pricing, ["PRICE"]).copy()
    p["PRICE"] = p["PRICE"].fillna(0.0)

    m_agg = _market_avg_price(market)
    rate = _recent_sales_rate(sales, lookback_steps=3)

    inv = _safe_numeric(inventory, ["STOCK"]).copy() if not inventory.empty else pd.DataFrame()
    inv_prod = inv[inv["MATERIAL_NUMBER"].astype(str).str.contains(r"-F\d+", regex=True, na=False)].copy()
    inv_prod = (
        inv_prod.groupby("MATERIAL_NUMBER", dropna=False)["STOCK"]
        .sum()
        .reset_index()
        .rename(columns={"STOCK": "inventory_units"})
    )

    joined = p.merge(
        m_agg,
        on=["DISTRIBUTION_CHANNEL", "MATERIAL_DESCRIPTION"],
        how="left",
    ).merge(
        rate,
        on=["DISTRIBUTION_CHANNEL", "MATERIAL_DESCRIPTION"],
        how="left",
    ).merge(
        inv_prod[["MATERIAL_NUMBER", "inventory_units"]],
        on=["MATERIAL_NUMBER"],
        how="left",
    )

    suggestions: list[PriceSuggestion] = []
    for _, r in joined.iterrows():
        cur = float(r.get("PRICE") or 0.0)
        market_avg = r.get("market_avg_price")
        inv_units = r.get("inventory_units")
        recent_rate = r.get("recent_units_sold_per_step")

        # Conservative default: keep price.
        suggested = cur
        reason = "no change"

        # Compute "pressure" signals.
        low_stock = (inv_units is not None) and (not pd.isna(inv_units)) and float(inv_units) < 5000
        high_stock = (inv_units is not None) and (not pd.isna(inv_units)) and float(inv_units) > 20000

        if market_avg is not None and not pd.isna(market_avg):
            gap = float(cur - float(market_avg))

            # If we're meaningfully under market and stock is tight -> raise.
            if gap < -0.10 and low_stock:
                steps = min(max_steps, int(abs(gap) / price_step_eur) + 1)
                suggested = cur + steps * price_step_eur
                reason = "under market & low stock (capture margin)"
            # If we're above market and sitting on stock -> lower.
            elif gap > 0.10 and high_stock:
                steps = min(max_steps, int(abs(gap) / price_step_eur) + 1)
                suggested = max(0.01, cur - steps * price_step_eur)
                reason = "above market & high stock (stimulate demand)"
            # Small drift toward market otherwise.
            elif gap < -0.25:
                suggested = cur + price_step_eur
                reason = "far under market (drift up)"
            elif gap > 0.25:
                suggested = max(0.01, cur - price_step_eur)
                reason = "far above market (drift down)"

        suggestions.append(
            PriceSuggestion(
                distribution_channel=str(r.get("DISTRIBUTION_CHANNEL", "")),
                material_number=str(r.get("MATERIAL_NUMBER", "")),
                material_description=str(r.get("MATERIAL_DESCRIPTION", "")),
                current_price=cur,
                market_avg_price=float(market_avg) if market_avg is not None and not pd.isna(market_avg) else None,
                inventory_units=float(inv_units) if inv_units is not None and not pd.isna(inv_units) else None,
                recent_units_sold_per_step=float(recent_rate)
                if recent_rate is not None and not pd.isna(recent_rate)
                else None,
                suggested_price=float(round(suggested, 2)),
                reason=reason,
            )
        )

    # Sort: prioritize biggest absolute change.
    suggestions.sort(key=lambda s: abs(s.suggested_price - s.current_price), reverse=True)
    return suggestions


def _estimate_daily_demand_units(sales: pd.DataFrame) -> pd.DataFrame:
    """
    Estimate units/day per product using last 5 steps.
    This is a coarse proxy but stable enough for a first iteration.
    """
    if sales.empty:
        return pd.DataFrame(columns=["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION", "demand_units_per_day_est"])
    s = _safe_numeric(sales, ["QUANTITY"]).copy()
    s["step_id"] = _to_step_id(s)
    max_step = int(s["step_id"].max())
    window = s[s["step_id"] >= (max_step - 4)]
    agg = (
        window.groupby(["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION"], dropna=False)["QUANTITY"]
        .sum()
        .reset_index()
    )
    agg["demand_units_per_day_est"] = agg["QUANTITY"] / 5.0
    return agg.drop(columns=["QUANTITY"])


def _lot_round(qty: float, lot: int, lot_max: int) -> int:
    qty = max(0.0, float(qty))
    if qty <= 0:
        return 0
    rounded = int(math.ceil(qty / lot) * lot)
    return int(min(max(rounded, lot), lot_max))


def build_production_suggestions(
    *,
    sales: pd.DataFrame,
    inventory: pd.DataFrame,
    target_coverage_days: int,
    min_lot: int = 16000,
    max_lot: int = 48000,
    top_k: int = 6,
) -> list[ProductionSuggestion]:
    if inventory.empty:
        return []

    inv = _safe_numeric(inventory, ["STOCK"]).copy()
    inv_prod = inv[inv["MATERIAL_NUMBER"].astype(str).str.contains(r"-F\d+", regex=True, na=False)].copy()
    inv_prod = (
        inv_prod.groupby(["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION"], dropna=False)["STOCK"]
        .sum()
        .reset_index()
        .rename(columns={"STOCK": "inventory_units"})
    )

    demand = _estimate_daily_demand_units(sales)
    joined = inv_prod.merge(demand, on=["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION"], how="left")
    joined["demand_units_per_day_est"] = joined["demand_units_per_day_est"].fillna(0.0)
    joined["inventory_units"] = joined["inventory_units"].fillna(0.0)

    # Coverage = inventory / demand, guard division by zero
    joined["coverage_days"] = np.where(
        joined["demand_units_per_day_est"] > 0,
        joined["inventory_units"] / joined["demand_units_per_day_est"],
        np.inf,
    )

    # Need = target_coverage - current coverage
    joined["gap_days"] = target_coverage_days - joined["coverage_days"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    joined["needed_units"] = (joined["gap_days"].clip(lower=0) * joined["demand_units_per_day_est"]).fillna(0.0)
    joined["suggested_batch_units"] = joined["needed_units"].apply(lambda x: _lot_round(x, min_lot, max_lot))

    # Prioritize lowest coverage first, but require some demand signal or stockout
    joined["priority"] = (
        (joined["coverage_days"].replace(np.inf, 9999).clip(upper=9999) * -1)
        + (joined["demand_units_per_day_est"] / 10000.0)
    )

    cand = joined.sort_values(["coverage_days", "inventory_units"], ascending=[True, True]).head(top_k)
    out: list[ProductionSuggestion] = []
    for _, r in cand.iterrows():
        batch = int(r["suggested_batch_units"])
        if batch <= 0:
            continue
        out.append(
            ProductionSuggestion(
                material_number=str(r["MATERIAL_NUMBER"]),
                material_description=str(r["MATERIAL_DESCRIPTION"]),
                inventory_units=float(r["inventory_units"]),
                demand_units_per_day_est=float(r["demand_units_per_day_est"]),
                coverage_days=float(r["coverage_days"]) if np.isfinite(r["coverage_days"]) else 9999.0,
                suggested_batch_units=batch,
                reason=f"coverage<{target_coverage_days}d with lot constraints ({min_lot}-{max_lot})",
            )
        )
    return out


def _parse_pack_size_kg(material_number: str, material_description: str) -> float | None:
    # Expect "500g ..." or "1kg ..." in description
    desc = (material_description or "").lower()
    m = re.search(r"(\d+)\s*kg", desc)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+)\s*g", desc)
    if m:
        return float(m.group(1)) / 1000.0
    # Fallback based on material code pattern
    if str(material_number).endswith("-F1") or str(material_number).endswith("-F2"):
        return None
    return None


def _material_prefix_from_inventory(inventory: pd.DataFrame) -> str:
    if inventory.empty or "MATERIAL_NUMBER" not in inventory.columns:
        return "CC"
    s = inventory["MATERIAL_NUMBER"].astype(str)
    m = s.str.extract(r"^([A-Z0-9]+)-")[0].dropna()
    if not m.empty:
        return str(m.iloc[0])
    return "CC"


def _default_bom_kg_per_box(material_description: str, prefix: str) -> dict[str, float]:
    """
    Simple BOM proxy from the Preset slides:
      - 500g: 20% wheat, 30% oats, 20% flavor ingredient (nut/blueberry/strawberry/raisins)
      - original: no extra ingredient (only wheat+oats)
      - mixed: 30% fruits & nuts (requires all fruits/nut in reality; we approximate equally)

    Returns kg of each raw material per 1 finished box.
    """
    desc = (material_description or "").lower()
    pack = 0.5 if "500g" in desc else 1.0 if "1kg" in desc else 0.5

    wheat = 0.20 * pack
    oats = 0.30 * pack
    rest = max(pack - wheat - oats, 0.0)

    out: dict[str, float] = {f"{prefix}-R05": wheat, f"{prefix}-R06": oats}

    if "nut" in desc:
        out[f"{prefix}-R01"] = 0.20 * pack
    elif "blueberry" in desc:
        out[f"{prefix}-R02"] = 0.20 * pack
    elif "strawberry" in desc:
        out[f"{prefix}-R03"] = 0.20 * pack
    elif "raisin" in desc:
        out[f"{prefix}-R04"] = 0.20 * pack
    elif "mixed" in desc:
        # Approximate split of "fruits & nuts" across R01-R04
        each = 0.30 * pack / 4.0
        out[f"{prefix}-R01"] = each
        out[f"{prefix}-R02"] = each
        out[f"{prefix}-R03"] = each
        out[f"{prefix}-R04"] = each
    else:
        # original: no extra ingredient specified; keep wheat+oats only
        _ = rest

    return out


def build_procurement_suggestions(
    *,
    sales: pd.DataFrame,
    inventory: pd.DataFrame,
    suppliers: pd.DataFrame,
    independent_requirements: pd.DataFrame,
    target_coverage_days: int,
) -> list[ProcurementSuggestion]:
    """
    Procurement suggestions are computed as:
      target finished goods coverage -> implied raw material + packaging needs via BOM proxy,
      then compare vs current raw/packaging inventory.

    This is a first-pass heuristic until we integrate ERP-native BOM/requirements signals
    more tightly (e.g., via MRP outputs, planned orders, or BOM_Changes).
    """
    if inventory.empty:
        return []

    inv = _safe_numeric(inventory, ["STOCK"]).copy()

    inv_prod = inv[inv["MATERIAL_NUMBER"].astype(str).str.contains(r"-F\d+", regex=True, na=False)].copy()
    _ = inv[inv["MATERIAL_NUMBER"].astype(str).str.contains(r"-R\d+", regex=True, na=False)].copy()
    _ = inv[inv["MATERIAL_NUMBER"].astype(str).str.contains(r"-P\d+", regex=True, na=False)].copy()
    prefix = _material_prefix_from_inventory(inv)

    demand = _estimate_daily_demand_units(sales)
    prod = inv_prod.merge(demand, on=["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION"], how="left")
    prod["demand_units_per_day_est"] = prod["demand_units_per_day_est"].fillna(0.0)
    prod["STOCK"] = prod["STOCK"].fillna(0.0)

    # Desired finished goods target units
    prod["target_units"] = prod["demand_units_per_day_est"] * float(target_coverage_days)
    prod["gap_units"] = (prod["target_units"] - prod["STOCK"]).clip(lower=0)

    # Aggregate raw material needs
    raw_need: dict[str, float] = {}
    pack_need: dict[str, float] = {}
    for _, r in prod.iterrows():
        gap_units = float(r["gap_units"])
        if gap_units <= 0:
            continue
        mat_desc = str(r["MATERIAL_DESCRIPTION"])

        bom = _default_bom_kg_per_box(mat_desc, prefix=prefix)
        for raw_mat, kg_per_box in bom.items():
            raw_need[raw_mat] = raw_need.get(raw_mat, 0.0) + gap_units * float(kg_per_box)

        # Packaging: 1 box + 1 bag per unit
        if "500g" in mat_desc.lower():
            pack_need[f"{prefix}-P03"] = pack_need.get(f"{prefix}-P03", 0.0) + gap_units
            pack_need[f"{prefix}-P04"] = pack_need.get(f"{prefix}-P04", 0.0) + gap_units
        else:
            pack_need[f"{prefix}-P01"] = pack_need.get(f"{prefix}-P01", 0.0) + gap_units
            pack_need[f"{prefix}-P02"] = pack_need.get(f"{prefix}-P02", 0.0) + gap_units

    # Build suggestion list by comparing to inventory.
    inv_lookup = (
        inv.set_index("MATERIAL_NUMBER")[["MATERIAL_DESCRIPTION", "STOCK", "UNIT"]]
        if not inv.empty
        else pd.DataFrame()
    )

    suggestions: list[ProcurementSuggestion] = []
    for mat, need in {**raw_need, **pack_need}.items():
        if mat not in inv_lookup.index:
            continue
        cur = float(pd.to_numeric(inv_lookup.loc[mat, "STOCK"], errors="coerce") or 0.0)
        unit = str(inv_lookup.loc[mat, "UNIT"])
        desc = str(inv_lookup.loc[mat, "MATERIAL_DESCRIPTION"])
        target = float(cur + max(need - cur, 0.0))
        buy = max(need - cur, 0.0)

        if buy <= 0:
            continue

        suggestions.append(
            ProcurementSuggestion(
                material_number=str(mat),
                material_description=desc,
                unit=unit,
                inventory=cur,
                target=need,
                suggested_purchase_qty=float(round(buy, 3)),
                reason=f"coverage target {target_coverage_days}d implies additional requirement",
            )
        )

    # Sort by biggest suggested quantity
    suggestions.sort(key=lambda s: s.suggested_purchase_qty, reverse=True)
    return suggestions[:20]


def build_action_tips(
    *,
    sales: pd.DataFrame,
    market: pd.DataFrame,
    pricing: pd.DataFrame,
    inventory: pd.DataFrame,
    suppliers: pd.DataFrame,
    independent_requirements: pd.DataFrame,
    price_step_eur: float,
    max_price_steps: int,
    target_coverage_days: int,
) -> list[ActionTip]:
    """
    Produce a small set of human-readable, prioritized tips for the current step.
    Heuristics are conservative and designed to be actionable even with limited info.
    """
    tips: list[ActionTip] = []

    inv = _safe_numeric(inventory, ["STOCK"]).copy() if not inventory.empty else pd.DataFrame()
    if not inv.empty:
        inv_prod = inv[inv["MATERIAL_NUMBER"].astype(str).str.contains(r"-F\d+", regex=True, na=False)].copy()
        inv_prod["STOCK"] = inv_prod["STOCK"].fillna(0.0)
        stockouts = inv_prod[inv_prod["STOCK"] <= 0].copy()
        if not stockouts.empty:
            items = stockouts.head(6)[["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION"]].astype(str)
            names = ", ".join((items["MATERIAL_NUMBER"] + " " + items["MATERIAL_DESCRIPTION"]).tolist())
            tips.append(
                ActionTip(
                    priority=100,
                    category="stockout",
                    material_number=None,
                    title="Stockouts vermeiden (Profit-Leak)",
                    suggested_action="Priorisiere sofort Produktion/Transfers/Verfügbarkeit für: " + names,
                    rationale="Ohne Bestand keine Sales; jede verpasste Nachfrage geht direkt an Wettbewerber.",
                )
            )

    # Use current-step margin signal (if available) to identify best/worst performers
    if not sales.empty:
        s = _safe_numeric(sales, ["NET_VALUE", "COST", "QUANTITY", "NET_PRICE"]).copy()
        s["step_id"] = _to_step_id(s)
        latest_step = int(s["step_id"].max())
        ss = s[s["step_id"] == latest_step].copy()
        if not ss.empty:
            by_prod = (
                ss.groupby(["DISTRIBUTION_CHANNEL", "MATERIAL_NUMBER", "MATERIAL_DESCRIPTION"], dropna=False)
                .agg(units=("QUANTITY", "sum"), revenue=("NET_VALUE", "sum"), cost=("COST", "sum"), price=("NET_PRICE", "mean"))
                .reset_index()
            )
            by_prod["margin"] = by_prod["revenue"] - by_prod["cost"]
            by_prod["margin_per_unit"] = np.where(by_prod["units"] > 0, by_prod["margin"] / by_prod["units"], np.nan)

            best = by_prod.sort_values("margin", ascending=False).head(3)
            worst = by_prod.sort_values("margin", ascending=True).head(3)

            if not best.empty:
                top_names = ", ".join(
                    (best["MATERIAL_NUMBER"].astype(str) + " " + best["MATERIAL_DESCRIPTION"].astype(str)).tolist()
                )
                tips.append(
                    ActionTip(
                        priority=85,
                        category="focus",
                        material_number=None,
                        title="Fokus auf Top-Margen-Produkte",
                        suggested_action=f"Stelle Verfügbarkeit sicher (Produktion/Einkauf) und teste vorsichtige Preiserhöhungen für: {top_names}",
                        rationale="Diese Produkte tragen aktuell den größten Margenbeitrag im letzten Step.",
                    )
                )
            if not worst.empty:
                low_names = ", ".join(
                    (worst["MATERIAL_NUMBER"].astype(str) + " " + worst["MATERIAL_DESCRIPTION"].astype(str)).tolist()
                )
                tips.append(
                    ActionTip(
                        priority=55,
                        category="fix",
                        material_number=None,
                        title="Margenfresser identifizieren",
                        suggested_action=f"Prüfe Preis vs Markt und Kosten für: {low_names} (nicht unter Cost verkaufen).",
                        rationale="Negative/geringe Margen senken Profit und Company Valuation.",
                    )
                )

    price_s = build_price_suggestions(
        sales=sales,
        market=market,
        pricing=pricing,
        inventory=inventory,
        price_step_eur=price_step_eur,
        max_steps=max_price_steps,
    )
    for ps in price_s[:5]:
        delta = ps.suggested_price - ps.current_price
        if abs(delta) < 1e-9:
            continue
        direction = "raise" if delta > 0 else "lower"
        tips.append(
            ActionTip(
                priority=70 if direction == "raise" else 60,
                category="pricing",
                material_number=ps.material_number,
                title=f"Pricing: {ps.material_number} {ps.material_description} (DC {ps.distribution_channel})",
                suggested_action=f"Setze {ps.material_number} Preis von {ps.current_price:.2f} → {ps.suggested_price:.2f} EUR",
                rationale=f"{ps.reason}. Market avg={ps.market_avg_price if ps.market_avg_price is not None else 'n/a'}, inv={ps.inventory_units if ps.inventory_units is not None else 'n/a'}",
            )
        )

    prod_s = build_production_suggestions(
        sales=sales,
        inventory=inventory,
        target_coverage_days=target_coverage_days,
    )
    for pr in prod_s[:5]:
        tips.append(
            ActionTip(
                priority=80,
                category="production",
                material_number=pr.material_number,
                title=f"Production: {pr.material_number} {pr.material_description}",
                suggested_action=f"Plane/Release {pr.material_number} Batch ≈ {pr.suggested_batch_units:,} units",
                rationale=f"Coverage ≈ {pr.coverage_days:.1f}d; Ziel={target_coverage_days}d. {pr.reason}",
            )
        )

    proc_s = build_procurement_suggestions(
        sales=sales,
        inventory=inventory,
        suppliers=suppliers,
        independent_requirements=independent_requirements,
        target_coverage_days=target_coverage_days,
    )
    for po in proc_s[:8]:
        tips.append(
            ActionTip(
                priority=65,
                category="procurement",
                material_number=po.material_number,
                title=f"Procure: {po.material_number} {po.material_description}",
                suggested_action=f"Kaufe {po.material_number} ≈ {po.suggested_purchase_qty:,} {po.unit}",
                rationale=f"Inventory={po.inventory:g} {po.unit}; Bedarf≈{po.target:g} {po.unit}. {po.reason}",
            )
        )

    # De-duplicate by title, keep highest priority
    best_by_title: dict[str, ActionTip] = {}
    for t in tips:
        prev = best_by_title.get(t.title)
        if prev is None or t.priority > prev.priority:
            best_by_title[t.title] = t
    out = sorted(best_by_title.values(), key=lambda x: x.priority, reverse=True)
    return out[:20]


def _latest_company_state(company_valuation: pd.DataFrame) -> dict[str, float | str | None]:
    if company_valuation.empty:
        return {}
    cv = _safe_numeric(
        company_valuation,
        [
            "SIM_ELAPSED_STEPS",
            "SIM_STEP",
            "BANK_CASH_ACCOUNT",
            "ACCOUNTS_RECEIVABLE",
            "BANK_LOAN",
            "ACCOUNTS_PAYABLE",
            "PROFIT",
            "DEBT_LOADING",
            "COMPANY_VALUATION",
        ],
    ).copy()
    if "SIM_ELAPSED_STEPS" in cv.columns:
        cv = cv.sort_values("SIM_ELAPSED_STEPS")
    row = cv.iloc[-1].to_dict()
    return row


def _carbon_cost_last_5days(financial_postings: pd.DataFrame) -> float:
    if financial_postings.empty:
        return 0.0
    fp = _safe_numeric(financial_postings, ["SIM_ELAPSED_STEPS", "AMOUNT"]).copy()
    fp["step_id"] = _to_step_id(fp)
    max_step = int(fp["step_id"].max()) if not fp.empty else 0
    window = fp[fp["step_id"] >= max_step - 4].copy()
    # Heuristic: carbon-related postings show up with GL names containing "Carbon"
    mask = window["GL_ACCOUNT_NAME"].astype(str).str.contains("carbon", case=False, na=False)
    amt = pd.to_numeric(window.loc[mask, "AMOUNT"], errors="coerce").fillna(0.0).sum()
    return float(amt)


def build_investment_suggestions(
    *,
    company_valuation: pd.DataFrame,
    financial_postings: pd.DataFrame,
) -> list[InvestmentSuggestion]:
    """
    Conservative guidance for Preset 3 (Sustainability).
    We only recommend investments when there's a plausible short-term payback or clear risk reduction.
    """
    state = _latest_company_state(company_valuation)
    cash = float(state.get("BANK_CASH_ACCOUNT") or 0.0) if state else 0.0
    profit = float(state.get("PROFIT") or 0.0) if state else 0.0
    debt_loading = float(state.get("DEBT_LOADING") or 0.0) if state else 0.0
    credit_rating = str(state.get("CREDIT_RATING")) if state and state.get("CREDIT_RATING") is not None else None

    carbon_cost_5d = _carbon_cost_last_5days(financial_postings)

    out: list[InvestmentSuggestion] = []

    # Small sustainability investments (JobAid): cost 10k, 15% reduction, max 45%.
    for inv_name in ["Sustainable Manufacturing", "Freight Fleet Improvement"]:
        cost = 10_000.0
        if carbon_cost_5d > 0:
            saving_5d = 0.15 * carbon_cost_5d
            payback_days = cost / saving_5d * 5.0 if saving_5d > 0 else None
        else:
            saving_5d = None
            payback_days = None

        if cash < cost * 3:
            rec = "wait (cash buffer too low)"
        elif saving_5d is None:
            rec = "consider (carbon costs unknown yet)"
        elif payback_days is not None and payback_days <= 20:
            rec = "buy now (fast payback via carbon savings)"
        else:
            rec = "wait (payback unclear/slow)"

        out.append(
            InvestmentSuggestion(
                investment=inv_name,
                cost_eur=cost,
                estimated_saving_eur_per_5days=float(saving_5d) if saving_5d is not None else None,
                est_payback_days=float(payback_days) if payback_days is not None else None,
                recommendation=rec,
            )
        )

    # Large investments: setup time reduction / capacity increase are expensive and usually hurt early valuation.
    out.append(
        InvestmentSuggestion(
            investment="Setup Time Reduction (ZFB50)",
            cost_eur=50_000.0,
            estimated_saving_eur_per_5days=None,
            est_payback_days=None,
            recommendation="wait (only if you have frequent product switches causing lost capacity)",
        )
    )
    out.append(
        InvestmentSuggestion(
            investment="Capacity Increase (ZFB50)",
            cost_eur=1_000_000.0,
            estimated_saving_eur_per_5days=None,
            est_payback_days=None,
            recommendation="avoid early (very high cost; buy only when capacity is the bottleneck)",
        )
    )

    # If profit is strongly negative and credit rating deteriorates, preserve cash.
    if profit < 0 and cash < 500_000:
        for i, s in enumerate(out):
            if s.cost_eur >= 50_000:
                out[i] = InvestmentSuggestion(
                    investment=s.investment,
                    cost_eur=s.cost_eur,
                    estimated_saving_eur_per_5days=s.estimated_saving_eur_per_5days,
                    est_payback_days=s.est_payback_days,
                    recommendation="avoid (profit negative + low cash)",
                )

    return out


def _storage_area_map(current_game_rules: pd.DataFrame) -> dict[str, str]:
    if current_game_rules.empty:
        return {}
    gr = current_game_rules.copy()
    sl = gr[
        (gr.get("ELEMENT", "").astype(str) == "Storage_Location")
        & (gr.get("DETAIL", "").notna())
        & (gr.get("VALUE", "").notna())
    ].copy()
    out: dict[str, str] = {}
    for _, r in sl.iterrows():
        detail = str(r.get("DETAIL", "")).strip()
        value = str(r.get("VALUE", "")).strip()
        if detail:
            out[detail] = value
    return out


def _transfer_cost_fixed(current_game_rules: pd.DataFrame, default_cost: float = 1000.0) -> float:
    if current_game_rules.empty:
        return float(default_cost)
    gr = current_game_rules.copy()
    mask = (
        gr.get("ELEMENT", "").astype(str).str.contains("transfer_cost", case=False, na=False)
        | gr.get("DETAIL", "").astype(str).str.contains("between storage locations", case=False, na=False)
    )
    m = gr.loc[mask].copy()
    if m.empty:
        return float(default_cost)
    val = pd.to_numeric(m.get("VALUE"), errors="coerce").dropna()
    if val.empty:
        return float(default_cost)
    return float(val.iloc[0])


def _location_to_area_fallback(storage_location: str) -> str:
    s = str(storage_location or "").upper()
    if s.endswith("N"):
        return "North"
    if s.endswith("S"):
        return "South"
    if s.endswith("W"):
        return "West"
    return "Unknown"


def build_transfer_suggestions(
    *,
    inventory: pd.DataFrame,
    market: pd.DataFrame,
    current_game_rules: pd.DataFrame,
    co2e_penalty_eur_per_unit: float = 0.02,
    demand_lookback_periods: int = 3,
    target_coverage_periods: int = 2,
    max_suggestions: int = 12,
) -> list[TransferSuggestion]:
    """
    Recommend inter-region stock transfers:
      score ~= qty * expected margin capture - fixed transfer cost - qty * CO2e penalty
    with a demand/coverage guard to avoid draining source locations too much.
    """
    if inventory.empty or market.empty:
        return []

    inv = _safe_numeric(inventory, ["STOCK"]).copy()
    inv = inv[inv["MATERIAL_NUMBER"].astype(str).str.contains(r"-F\d+", regex=True, na=False)].copy()
    if inv.empty:
        return []

    area_map = _storage_area_map(current_game_rules)
    inv["area"] = inv["STORAGE_LOCATION"].astype(str).map(area_map).fillna(
        inv["STORAGE_LOCATION"].astype(str).map(_location_to_area_fallback)
    )
    inv["STOCK"] = inv["STOCK"].fillna(0.0)

    m = _safe_numeric(market, ["QUANTITY", "AVERAGE_PRICE", "SIM_PERIOD"]).copy()
    m["SIM_PERIOD"] = pd.to_numeric(m.get("SIM_PERIOD"), errors="coerce").fillna(0).astype(int)
    max_period = int(m["SIM_PERIOD"].max()) if not m.empty else 0
    win = m[m["SIM_PERIOD"] >= (max_period - max(demand_lookback_periods, 1) + 1)].copy()
    if win.empty:
        win = m.copy()

    demand = (
        win.groupby(["MATERIAL_DESCRIPTION", "AREA"], dropna=False)["QUANTITY"]
        .sum()
        .reset_index()
        .rename(columns={"QUANTITY": "demand_qty_window"})
    )
    demand["demand_per_period"] = demand["demand_qty_window"] / float(max(demand_lookback_periods, 1))

    # Regional pricing is not directly controllable. We estimate value by expected margin capture,
    # not by area-specific price differences.
    sales_proxy = (
        win.groupby(["MATERIAL_DESCRIPTION"], dropna=False)
        .apply(
            lambda g: pd.Series(
                {
                    "margin_proxy_per_unit": max(float(g["AVERAGE_PRICE"].mean()) * 0.25, 0.10),
                }
            )
        )
        .reset_index()
    )

    inv_loc = (
        inv.groupby(
            ["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION", "STORAGE_LOCATION", "area"],
            dropna=False,
        )["STOCK"]
        .sum()
        .reset_index()
    )
    inv_loc = inv_loc.merge(
        demand[["MATERIAL_DESCRIPTION", "AREA", "demand_per_period"]],
        left_on=["MATERIAL_DESCRIPTION", "area"],
        right_on=["MATERIAL_DESCRIPTION", "AREA"],
        how="left",
    ).merge(
        sales_proxy[["MATERIAL_DESCRIPTION", "margin_proxy_per_unit"]],
        left_on=["MATERIAL_DESCRIPTION"],
        right_on=["MATERIAL_DESCRIPTION"],
        how="left",
    )
    inv_loc["demand_per_period"] = inv_loc["demand_per_period"].fillna(0.0)
    inv_loc["margin_proxy_per_unit"] = inv_loc["margin_proxy_per_unit"].fillna(0.10)

    transfer_cost = _transfer_cost_fixed(current_game_rules)
    out: list[TransferSuggestion] = []

    for mat, g in inv_loc.groupby(["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION"], dropna=False):
        g = g.copy()
        g["target_stock"] = g["demand_per_period"] * float(target_coverage_periods)
        g["deficit"] = (g["target_stock"] - g["STOCK"]).clip(lower=0.0)
        g["surplus"] = (g["STOCK"] - g["target_stock"]).clip(lower=0.0)

        deficits = g[g["deficit"] > 0].sort_values("deficit", ascending=False)
        surpluses = g[g["surplus"] > 0].sort_values("surplus", ascending=False)
        if deficits.empty or surpluses.empty:
            continue

        for d_idx, d in deficits.iterrows():
            needed = float(d["deficit"])
            if needed <= 0:
                continue
            for s_idx, s in surpluses.iterrows():
                available = float(s["surplus"])
                if available <= 0:
                    continue
                qty = min(needed, available)
                if qty <= 0:
                    continue
                margin_capture = float(d["margin_proxy_per_unit"])
                co2_penalty = float(co2e_penalty_eur_per_unit) * qty
                net_gain = qty * margin_capture - float(transfer_cost) - co2_penalty

                # Keep strong recommendations only; allows slight negative only for critical stockout risks.
                deficit_ratio = float(d["deficit"] / max(d["target_stock"], 1.0))
                urgency = "high" if deficit_ratio >= 0.75 else "medium" if deficit_ratio >= 0.35 else "low"
                if net_gain < 0 and urgency != "high":
                    continue

                out.append(
                    TransferSuggestion(
                        material_number=str(mat[0]),
                        material_description=str(mat[1]),
                        from_storage_location=str(s["STORAGE_LOCATION"]),
                        to_storage_location=str(d["STORAGE_LOCATION"]),
                        to_area=str(d["area"]),
                        estimated_qty=float(round(qty, 0)),
                        transfer_cost_eur=float(transfer_cost),
                        co2_penalty_eur=float(round(co2_penalty, 2)),
                        expected_margin_eur_per_unit=float(round(margin_capture, 3)),
                        expected_net_gain_eur=float(round(net_gain, 2)),
                        urgency=urgency,
                        rationale=(
                            f"demand deficit in {d['area']} with low coverage; "
                            f"includes fixed transfer cost={transfer_cost:.0f} and CO2e penalty."
                        ),
                    )
                )

                needed -= qty
                g.at[s_idx, "surplus"] = max(0.0, float(g.at[s_idx, "surplus"]) - qty)
                if needed <= 0:
                    break
            g.at[d_idx, "deficit"] = max(0.0, needed)

    out.sort(
        key=lambda x: (
            0 if x.urgency == "high" else 1 if x.urgency == "medium" else 2,
            -x.expected_net_gain_eur,
        )
    )
    return out[:max_suggestions]


def build_advertising_suggestions(
    *,
    sales: pd.DataFrame,
    market: pd.DataFrame,
    inventory: pd.DataFrame,
    marketing_expenses: pd.DataFrame,
    max_suggestions: int = 12,
) -> list[AdvertisingSuggestion]:
    if sales.empty or market.empty:
        return []

    s = _safe_numeric(sales, ["QUANTITY", "SIM_PERIOD"]).copy()
    m = _safe_numeric(market, ["QUANTITY", "SIM_PERIOD"]).copy()
    inv = _safe_numeric(inventory, ["STOCK"]).copy() if not inventory.empty else pd.DataFrame()
    ad = _safe_numeric(marketing_expenses, ["AMOUNT", "SIM_PERIOD"]).copy() if not marketing_expenses.empty else pd.DataFrame()

    max_period = int(pd.to_numeric(m.get("SIM_PERIOD"), errors="coerce").fillna(0).max()) if not m.empty else 0
    period_min = max_period - 2

    s_win = s[pd.to_numeric(s.get("SIM_PERIOD"), errors="coerce").fillna(0) >= period_min].copy()
    m_win = m[pd.to_numeric(m.get("SIM_PERIOD"), errors="coerce").fillna(0) >= period_min].copy()
    ad_win = ad[pd.to_numeric(ad.get("SIM_PERIOD"), errors="coerce").fillna(0) >= period_min].copy() if not ad.empty else ad

    our = (
        s_win.groupby(["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION", "AREA"], dropna=False)["QUANTITY"]
        .sum()
        .reset_index()
        .rename(columns={"QUANTITY": "our_qty"})
    )
    total = (
        m_win.groupby(["MATERIAL_DESCRIPTION", "AREA"], dropna=False)["QUANTITY"]
        .sum()
        .reset_index()
        .rename(columns={"QUANTITY": "market_qty"})
    )

    base = our.merge(total, on=["MATERIAL_DESCRIPTION", "AREA"], how="left")
    base["market_qty"] = base["market_qty"].fillna(0.0)
    base["share_pct"] = np.where(base["market_qty"] > 0, 100.0 * base["our_qty"] / base["market_qty"], 0.0)

    if not inv.empty:
        inv_fg = (
            inv[inv["MATERIAL_NUMBER"].astype(str).str.contains(r"-F\d+", regex=True, na=False)]
            .groupby("MATERIAL_NUMBER", dropna=False)["STOCK"]
            .sum()
            .reset_index()
            .rename(columns={"STOCK": "inventory_units"})
        )
        base = base.merge(inv_fg, on="MATERIAL_NUMBER", how="left")
    else:
        base["inventory_units"] = 0.0
    base["inventory_units"] = base["inventory_units"].fillna(0.0)

    if not ad_win.empty:
        ad_agg = (
            ad_win.groupby(["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION", "AREA"], dropna=False)["AMOUNT"]
            .mean()
            .reset_index()
            .rename(columns={"AMOUNT": "current_ad_spend_eur"})
        )
        base = base.merge(ad_agg, on=["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION", "AREA"], how="left")
    else:
        base["current_ad_spend_eur"] = 0.0
    base["current_ad_spend_eur"] = base["current_ad_spend_eur"].fillna(0.0)

    out: list[AdvertisingSuggestion] = []
    for _, r in base.iterrows():
        market_qty = float(r["market_qty"])
        if market_qty <= 0:
            continue
        share = float(r["share_pct"])
        inventory_units = float(r["inventory_units"])
        # Avoid advertising stockouts.
        if inventory_units <= 0:
            continue

        # Heuristic target share by market attractiveness.
        target_share = 18.0 if market_qty >= 4000 else 14.0 if market_qty >= 2000 else 10.0
        share_gap = target_share - share
        if share_gap <= 0:
            continue

        cur_ad = float(r["current_ad_spend_eur"])
        suggested = max(cur_ad, 0.0)
        if share_gap >= 10:
            suggested = max(suggested, 5000.0)
            prio = "high"
        elif share_gap >= 5:
            suggested = max(suggested, 2500.0)
            prio = "medium"
        else:
            suggested = max(suggested, 1000.0)
            prio = "low"

        out.append(
            AdvertisingSuggestion(
                material_number=str(r["MATERIAL_NUMBER"]),
                material_description=str(r["MATERIAL_DESCRIPTION"]),
                area=str(r["AREA"]),
                recent_market_qty=market_qty,
                recent_our_qty=float(r["our_qty"]),
                recent_share_pct=float(round(share, 2)),
                target_share_pct=float(target_share),
                current_ad_spend_eur=float(round(cur_ad, 2)),
                suggested_ad_spend_eur=float(round(suggested, 2)),
                priority=prio,
                rationale="regional demand capture via advertising (pricing is not region-specific).",
            )
        )

    out.sort(key=lambda x: (0 if x.priority == "high" else 1 if x.priority == "medium" else 2, -(x.target_share_pct - x.recent_share_pct)))
    return out[:max_suggestions]

