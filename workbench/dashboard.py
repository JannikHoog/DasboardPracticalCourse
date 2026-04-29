from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Callable

# Make imports robust even when Streamlit is launched from a different
# Python environment (e.g. Anaconda base) where the project root is not on PYTHONPATH.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from workbench.lib.duckdb_lake import ingest_latest_snapshots_to_duckdb
from workbench.lib.loaders import LatestSnapshots, load_latest_snapshots
from workbench.lib.recommendations import (
    ProcurementSuggestion,
    ProductionSuggestion,
    PriceSuggestion,
    ActionTip,
    build_action_tips,
    InvestmentSuggestion,
    build_investment_suggestions,
    build_procurement_suggestions,
    build_production_suggestions,
    build_price_suggestions,
    TransferSuggestion,
    build_transfer_suggestions,
    AdvertisingSuggestion,
    build_advertising_suggestions,
)


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path = Path("automation/data")
    duckdb_path: Path = Path("workbench/lake/erpsim_lake.duckdb")
    persist_ingested_snapshots: bool = True
    auto_refresh_seconds: int = 30


def _safe_to_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def _step_id(df: pd.DataFrame) -> pd.Series:
    if "SIM_ELAPSED_STEPS" in df.columns:
        return pd.to_numeric(df["SIM_ELAPSED_STEPS"], errors="coerce").fillna(0).astype(int)
    rnd = pd.to_numeric(df.get("SIM_ROUND", 0), errors="coerce").fillna(0).astype(int)
    step = pd.to_numeric(df.get("SIM_STEP", 0), errors="coerce").fillna(0).astype(int)
    return rnd * 100 + step


def _render_header(snap: LatestSnapshots) -> None:
    st.title("ERPsim Decision Dashboard (Workbench)")
    st.caption("Ziel: Trends erkennen und konkrete Handlungs-Vorschläge (Preis, Produktion, Einkauf).")
    st.info(
        "Side-Disruptors sind in dieser Runde noch nicht verfügbar. "
        "Die Disruptor-Kachel ist daher aktuell nur ein Platzhalter."
    )

    with st.expander("Data snapshot status", expanded=False):
        st.write(
            {
                "sales": str(snap.sales_path) if snap.sales_path else None,
                "market": str(snap.market_path) if snap.market_path else None,
                "inventory": str(snap.current_inventory_path) if snap.current_inventory_path else None,
                "pricing": str(snap.pricing_conditions_path) if snap.pricing_conditions_path else None,
                "suppliers": str(snap.current_suppliers_prices_path)
                if snap.current_suppliers_prices_path
                else None,
                "independent_requirements": str(snap.independent_requirements_path)
                if snap.independent_requirements_path
                else None,
                "production_orders": str(snap.production_orders_path) if snap.production_orders_path else None,
                "purchase_orders": str(snap.purchase_orders_path) if snap.purchase_orders_path else None,
                "production": str(snap.production_path) if snap.production_path else None,
                "stock_transfers": str(snap.stock_transfers_path) if snap.stock_transfers_path else None,
                "marketing_expenses": str(snap.marketing_expenses_path) if snap.marketing_expenses_path else None,
                "financial_postings": str(snap.financial_postings_path) if snap.financial_postings_path else None,
                "company_valuation": str(snap.company_valuation_path) if snap.company_valuation_path else None,
                "current_game_rules": str(snap.current_game_rules_path) if snap.current_game_rules_path else None,
            }
        )


@st.cache_data(show_spinner=False)
def _read_csv_cached(path: str, mtime_ns: int) -> pd.DataFrame:
    # Cache invalidates automatically when file mtime changes.
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _load_frames_fast(snap: LatestSnapshots) -> dict[str, pd.DataFrame]:
    mapping = {
        "sales": snap.sales_path,
        "market": snap.market_path,
        "current_inventory": snap.current_inventory_path,
        "current_inventory_kpi": snap.current_inventory_kpi_path,
        "pricing_conditions": snap.pricing_conditions_path,
        "current_suppliers_prices": snap.current_suppliers_prices_path,
        "independent_requirements": snap.independent_requirements_path,
        "production_orders": snap.production_orders_path,
        "purchase_orders": snap.purchase_orders_path,
        "production": snap.production_path,
        "stock_transfers": snap.stock_transfers_path,
        "marketing_expenses": snap.marketing_expenses_path,
        "financial_postings": snap.financial_postings_path,
        "company_valuation": snap.company_valuation_path,
        "current_game_rules": snap.current_game_rules_path,
    }
    frames: dict[str, pd.DataFrame] = {}
    for k, p in mapping.items():
        if not p or not Path(p).exists():
            frames[k] = pd.DataFrame()
            continue
        stat = Path(p).stat()
        frames[k] = _read_csv_cached(str(p), stat.st_mtime_ns)
    return frames


def _kpis(sales: pd.DataFrame, inv: pd.DataFrame) -> None:
    c1, c2, c3, c4 = st.columns(4)

    if sales.empty:
        c1.metric("Latest step", "n/a")
        c2.metric("Revenue (total)", "n/a")
        c3.metric("Margin (total)", "n/a")
    else:
        sales = _safe_to_numeric(sales, ["NET_VALUE", "COST", "QUANTITY"])
        sales["step_id"] = _step_id(sales)
        latest_step = int(sales["step_id"].max())
        latest_sales = sales[sales["step_id"] == latest_step]
        revenue = float(latest_sales["NET_VALUE"].sum())
        margin = float((latest_sales["NET_VALUE"] - latest_sales["COST"]).sum())

        c1.metric("Latest step", latest_step)
        c2.metric("Revenue (latest step)", f"{revenue:,.0f} EUR")
        c3.metric("Margin (latest step)", f"{margin:,.0f} EUR")

    if inv.empty:
        c4.metric("Stockout products", "n/a")
    else:
        inv = _safe_to_numeric(inv, ["STOCK"])
        stockout_products = int((inv["STOCK"].fillna(0) <= 0).sum())
        c4.metric("Stockout items (inventory)", stockout_products)


def _trends_sales(sales: pd.DataFrame, key_prefix: str = "sales_trends") -> None:
    st.subheader("Nachfrage-Trends (Sales)")
    if sales.empty:
        st.warning("Keine Sales-Daten im Snapshot.")
        return

    sales = _safe_to_numeric(sales, ["NET_VALUE", "COST", "QUANTITY", "NET_PRICE"])
    sales["step_id"] = _step_id(sales)
    view = (
        sales.groupby(
            ["step_id", "DISTRIBUTION_CHANNEL", "MATERIAL_NUMBER", "MATERIAL_DESCRIPTION"],
            dropna=False,
        )
        .agg(qty=("QUANTITY", "sum"), revenue=("NET_VALUE", "sum"), realized_price=("NET_PRICE", "mean"))
        .reset_index()
        .sort_values("step_id")
    )

    dcs = [10, 12, 14]
    cols = st.columns(3)
    for i, dc in enumerate(dcs):
        with cols[i]:
            st.markdown(f"**DC {dc}**")
            vdc = view[view["DISTRIBUTION_CHANNEL"] == dc]
            if vdc.empty:
                st.info("Keine Sales.")
                continue

            latest_step = int(vdc["step_id"].max())
            latest = vdc[vdc["step_id"] == latest_step].copy()
            latest = latest.sort_values("revenue", ascending=False)
            st.caption(f"Latest step: {latest_step}")
            st.dataframe(
                latest[
                    [
                        "MATERIAL_NUMBER",
                        "MATERIAL_DESCRIPTION",
                        "qty",
                        "revenue",
                        "realized_price",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

            fig = px.line(
                vdc,
                x="step_id",
                y="qty",
                color="MATERIAL_NUMBER",
                title=f"Units/step (DC {dc})",
                markers=True,
            )
            st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_dc_{dc}")


def _trends_prices(pricing: pd.DataFrame, market: pd.DataFrame) -> None:
    st.subheader("Preis-Trends & Marktvergleich")
    if pricing.empty:
        st.warning("Keine Current_Pricing_Conditions im Snapshot.")
        return

    p = _safe_to_numeric(pricing, ["PRICE"])
    p = p.rename(columns={"PRICE": "our_list_price"})

    if market.empty:
        cols = st.columns(3)
        for i, dc in enumerate([10, 12, 14]):
            with cols[i]:
                st.markdown(f"**DC {dc}**")
                pdc = p[p["DISTRIBUTION_CHANNEL"] == dc].copy()
                if pdc.empty:
                    st.info("Keine Preise.")
                    continue
                st.dataframe(
                    pdc[["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION", "our_list_price"]].sort_values(
                        "MATERIAL_NUMBER"
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
        return

    m = _safe_to_numeric(market, ["AVERAGE_PRICE", "QUANTITY"])
    m_agg = (
        m.groupby(["DISTRIBUTION_CHANNEL", "MATERIAL_DESCRIPTION"], dropna=False)
        .apply(
            lambda g: pd.Series(
                {
                    "market_avg_price": float(
                        np.average(g["AVERAGE_PRICE"], weights=g["QUANTITY"].clip(lower=0).fillna(0))
                    )
                    if g["QUANTITY"].fillna(0).sum() > 0
                    else float(g["AVERAGE_PRICE"].mean())
                }
            )
        )
        .reset_index()
    )

    joined = p.merge(
        m_agg,
        on=["DISTRIBUTION_CHANNEL", "MATERIAL_DESCRIPTION"],
        how="left",
    )
    joined["gap_vs_market"] = joined["our_list_price"] - joined["market_avg_price"]
    cols = st.columns(3)
    for i, dc in enumerate([10, 12, 14]):
        with cols[i]:
            st.markdown(f"**DC {dc}**")
            jdc = joined[joined["DISTRIBUTION_CHANNEL"] == dc].copy()
            if jdc.empty:
                st.info("Keine Daten.")
                continue
            jdc = jdc.sort_values("MATERIAL_NUMBER")
            st.dataframe(
                jdc[
                    [
                        "MATERIAL_NUMBER",
                        "MATERIAL_DESCRIPTION",
                        "our_list_price",
                        "market_avg_price",
                        "gap_vs_market",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )


def _market_overview(market: pd.DataFrame, pricing: pd.DataFrame) -> None:
    st.subheader("Marktdaten (Market) – pro Distribution Channel")
    if market.empty:
        st.warning("Keine Market-Daten im Snapshot.")
        return

    m = _safe_to_numeric(market, ["AVERAGE_PRICE", "QUANTITY", "NET_VALUE"])
    # Aggregate across AREA (region) at product + DC level for a single view.
    m_agg = (
        m.groupby(["DISTRIBUTION_CHANNEL", "MATERIAL_DESCRIPTION"], dropna=False)
        .apply(
            lambda g: pd.Series(
                {
                    "market_qty": float(pd.to_numeric(g["QUANTITY"], errors="coerce").fillna(0.0).sum()),
                    "market_net_value": float(pd.to_numeric(g["NET_VALUE"], errors="coerce").fillna(0.0).sum()),
                    "market_avg_price": float(
                        np.average(
                            pd.to_numeric(g["AVERAGE_PRICE"], errors="coerce").fillna(0.0),
                            weights=pd.to_numeric(g["QUANTITY"], errors="coerce").fillna(0.0).clip(lower=0.0),
                        )
                    )
                    if float(pd.to_numeric(g["QUANTITY"], errors="coerce").fillna(0.0).sum()) > 0
                    else float(pd.to_numeric(g["AVERAGE_PRICE"], errors="coerce").mean()),
                }
            )
        )
        .reset_index()
    )

    # Join product ids from pricing (market table doesn't include MATERIAL_NUMBER).
    if not pricing.empty:
        p = pricing[["DISTRIBUTION_CHANNEL", "MATERIAL_NUMBER", "MATERIAL_DESCRIPTION"]].drop_duplicates()
        m_agg = m_agg.merge(
            p,
            on=["DISTRIBUTION_CHANNEL", "MATERIAL_DESCRIPTION"],
            how="left",
        )
    else:
        m_agg["MATERIAL_NUMBER"] = None

    cols = st.columns(3)
    for i, dc in enumerate([10, 12, 14]):
        with cols[i]:
            st.markdown(f"**DC {dc}**")
            v = m_agg[m_agg["DISTRIBUTION_CHANNEL"] == dc].copy()
            if v.empty:
                st.info("Keine Marktdaten.")
                continue
            v = v.sort_values(["market_net_value", "market_qty"], ascending=False)
            st.dataframe(
                v[
                    [
                        "MATERIAL_NUMBER",
                        "MATERIAL_DESCRIPTION",
                        "market_qty",
                        "market_avg_price",
                        "market_net_value",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )


def _suggestions(
    sales: pd.DataFrame,
    market: pd.DataFrame,
    pricing: pd.DataFrame,
    inv: pd.DataFrame,
    suppliers: pd.DataFrame,
    indreq: pd.DataFrame,
    purchase_orders: pd.DataFrame,
    production_orders: pd.DataFrame,
    production: pd.DataFrame,
    current_game_rules: pd.DataFrame,
    marketing_expenses: pd.DataFrame,
) -> None:
    st.subheader("Handlungsvorschläge")

    c1, c2 = st.columns([2, 1])
    with c2:
        st.markdown("**Heuristik-Parameter**")
        target_coverage_days = st.number_input("Target coverage (days)", min_value=1, max_value=20, value=5, step=1)
        price_step_eur = st.number_input("Price step (EUR)", min_value=0.05, max_value=1.0, value=0.10, step=0.05)
        max_price_change_steps = st.number_input("Max steps per product", min_value=1, max_value=20, value=5, step=1)
        co2e_penalty_unit = st.number_input(
            "CO2e penalty per transferred unit (EUR)",
            min_value=0.0,
            max_value=1.0,
            value=0.02,
            step=0.01,
        )

    with c1:
        st.markdown("**Execution Monitor (über Einkauf/Produktion)**")
        e1, e2 = st.columns(2)
        with e1:
            st.markdown("**Purchase Orders Status**")
            if purchase_orders.empty:
                st.info("Keine Purchase-Order-Daten.")
            else:
                po = purchase_orders.copy()
                po["status_norm"] = po.get("STATUS", "").astype(str).str.lower()
                po["lag_flag"] = np.where(
                    po["status_norm"].str.contains("open|partial|late|delay", na=False),
                    "🔴 LAGGING",
                    "🟢 OK",
                )
                po_view = (
                    po.groupby(["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION", "STATUS", "lag_flag"], dropna=False)
                    .agg(ordered_qty=("QUANTITY", "sum"))
                    .reset_index()
                    .sort_values(["lag_flag", "ordered_qty"], ascending=[False, False])
                )
                st.dataframe(
                    po_view[
                        ["lag_flag", "MATERIAL_NUMBER", "MATERIAL_DESCRIPTION", "STATUS", "ordered_qty"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
        with e2:
            st.markdown("**Production Orders Progress**")
            if production_orders.empty:
                st.info("Keine Production-Order-Daten.")
            else:
                pr = _safe_to_numeric(production_orders, ["TARGET_QUANTITY", "CONFIRMED_QUANTITY"]).copy()
                pr["progress_pct"] = np.where(
                    pr["TARGET_QUANTITY"] > 0,
                    100.0 * pr["CONFIRMED_QUANTITY"] / pr["TARGET_QUANTITY"],
                    0.0,
                )
                pr["lag_flag"] = np.where(pr["progress_pct"] < 95.0, "🔴 LAGGING", "🟢 OK")
                pr_view = (
                    pr.groupby(["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION", "lag_flag"], dropna=False)
                    .agg(
                        target_qty=("TARGET_QUANTITY", "sum"),
                        confirmed_qty=("CONFIRMED_QUANTITY", "sum"),
                    )
                    .reset_index()
                )
                pr_view["progress_pct"] = np.where(
                    pr_view["target_qty"] > 0,
                    100.0 * pr_view["confirmed_qty"] / pr_view["target_qty"],
                    0.0,
                )
                pr_view = pr_view.sort_values(["lag_flag", "progress_pct"], ascending=[False, True])
                st.dataframe(
                    pr_view[
                        [
                            "lag_flag",
                            "MATERIAL_NUMBER",
                            "MATERIAL_DESCRIPTION",
                            "target_qty",
                            "confirmed_qty",
                            "progress_pct",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

        st.divider()

        tips: list[ActionTip] = build_action_tips(
            sales=sales,
            market=market,
            pricing=pricing,
            inventory=inv,
            suppliers=suppliers,
            independent_requirements=indreq,
            price_step_eur=float(price_step_eur),
            max_price_steps=int(max_price_change_steps),
            target_coverage_days=int(target_coverage_days),
        )
        st.markdown("**Top Tipps (profit-orientiert)**")
        if tips:
            st.dataframe(pd.DataFrame([t.__dict__ for t in tips]), use_container_width=True, hide_index=True)
        else:
            st.info("Noch keine Tipps ableitbar (prüfe, ob Sales/Market/Inventory im Snapshot vorhanden sind).")

        st.divider()

        price_s: list[PriceSuggestion] = build_price_suggestions(
            sales=sales,
            market=market,
            pricing=pricing,
            inventory=inv,
            price_step_eur=float(price_step_eur),
            max_steps=int(max_price_change_steps),
        )
        prod_s: list[ProductionSuggestion] = build_production_suggestions(
            sales=sales,
            inventory=inv,
            target_coverage_days=int(target_coverage_days),
        )
        proc_s: list[ProcurementSuggestion] = build_procurement_suggestions(
            sales=sales,
            inventory=inv,
            suppliers=suppliers,
            independent_requirements=indreq,
            target_coverage_days=int(target_coverage_days),
        )
        transfer_s: list[TransferSuggestion] = build_transfer_suggestions(
            inventory=inv,
            market=market,
            current_game_rules=current_game_rules,
            co2e_penalty_eur_per_unit=float(co2e_penalty_unit),
            demand_lookback_periods=3,
            target_coverage_periods=2,
        )
        ad_s: list[AdvertisingSuggestion] = build_advertising_suggestions(
            sales=sales,
            market=market,
            inventory=inv,
            marketing_expenses=marketing_expenses,
        )

        st.markdown("**Preis (VK32)**")
        st.caption("Hinweis: Preise werden nicht regional (AREA) gesteuert; Regionen steuerst du ueber Advertising.")
        if price_s:
            dfp = pd.DataFrame([s.__dict__ for s in price_s])
            dfp["price_delta"] = dfp["suggested_price"] - dfp["current_price"]
            dfp["urgent_price_flag"] = np.where(
                (dfp["price_delta"].abs() >= 0.30)
                | (dfp["inventory_units"].fillna(999999) <= 0)
                | (dfp["reason"].astype(str).str.contains("far under market|far above market", regex=True)),
                "🔴 URGENT",
                "🟡 monitor",
            )
            dfp = dfp.sort_values(
                ["urgent_price_flag", "price_delta"],
                ascending=[True, False],
                key=lambda s: s.astype(str),
            )
            cols = [
                "urgent_price_flag",
                "distribution_channel",
                "material_number",
                "material_description",
                "current_price",
                "suggested_price",
                "price_delta",
                "market_avg_price",
                "inventory_units",
                "recent_units_sold_per_step",
                "reason",
            ]
            st.dataframe(dfp[[c for c in cols if c in dfp.columns]], use_container_width=True, hide_index=True)
        else:
            st.info("Keine Preisvorschläge verfügbar.")

        st.markdown("**Produktion (CO41 / Planned orders)**")
        if prod_s:
            dfpr = pd.DataFrame([s.__dict__ for s in prod_s])
            cols = [
                "material_number",
                "material_description",
                "inventory_units",
                "demand_units_per_day_est",
                "coverage_days",
                "suggested_batch_units",
                "reason",
            ]
            st.dataframe(dfpr[[c for c in cols if c in dfpr.columns]], use_container_width=True, hide_index=True)
        else:
            st.info("Keine Produktionsvorschläge verfügbar.")

        st.markdown("**Einkauf (ZME12 / ME59N)**")
        if proc_s:
            dfpo = pd.DataFrame([s.__dict__ for s in proc_s])
            cols = [
                "material_number",
                "material_description",
                "suggested_purchase_qty",
                "unit",
                "inventory",
                "target",
                "reason",
            ]
            st.dataframe(dfpo[[c for c in cols if c in dfpo.columns]], use_container_width=True, hide_index=True)
        else:
            st.info("Keine Einkaufsvorschläge verfügbar.")

        st.markdown("**Stock Transfer (Regionen)**")
        if transfer_s:
            dft = pd.DataFrame([s.__dict__ for s in transfer_s])
            dft["priority"] = dft["urgency"].map({"high": "🔴 URGENT", "medium": "🟡 medium", "low": "🟢 low"})
            cols = [
                "priority",
                "material_number",
                "material_description",
                "from_storage_location",
                "to_storage_location",
                "to_area",
                "estimated_qty",
                "expected_margin_eur_per_unit",
                "transfer_cost_eur",
                "co2_penalty_eur",
                "expected_net_gain_eur",
                "rationale",
            ]
            st.dataframe(dft[[c for c in cols if c in dft.columns]], use_container_width=True, hide_index=True)
        else:
            st.info("Keine klaren Transferkandidaten (unter aktuellen Preis/CO2e/Cost-Constraints).")

        st.markdown("**Advertising (Regionen / Nachfrage steuern)**")
        if ad_s:
            dfa = pd.DataFrame([s.__dict__ for s in ad_s])
            dfa["priority_flag"] = dfa["priority"].map({"high": "🔴 URGENT", "medium": "🟡 medium", "low": "🟢 low"})
            cols = [
                "priority_flag",
                "material_number",
                "material_description",
                "area",
                "recent_market_qty",
                "recent_our_qty",
                "recent_share_pct",
                "target_share_pct",
                "current_ad_spend_eur",
                "suggested_ad_spend_eur",
                "rationale",
            ]
            st.dataframe(dfa[[c for c in cols if c in dfa.columns]], use_container_width=True, hide_index=True)
        else:
            st.info("Keine klaren Advertising-Kandidaten (oder kein verfuegbarer Bestand).")


def _investments(company_valuation: pd.DataFrame, financial_postings: pd.DataFrame) -> None:
    st.subheader("Investments (ZFB50) – Empfehlung")
    inv_s: list[InvestmentSuggestion] = build_investment_suggestions(
        company_valuation=company_valuation,
        financial_postings=financial_postings,
    )
    if inv_s:
        dfi = pd.DataFrame([s.__dict__ for s in inv_s])
        st.dataframe(dfi, use_container_width=True, hide_index=True)
    else:
        st.info("Keine Investment-Daten verfügbar (Company_Valuation / Financial_Postings fehlen).")


def _disruptor_placeholder() -> None:
    st.subheader("Disruptor Monitor (Placeholder)")
    st.write(
        {
            "status": "inactive (side disruptors not available this round)",
            "expected_sources": [
                "Weather (REST)",
                "Supplier stock market (REST)",
                "Energy market (Kafka)",
                "Water level (Kafka)",
                "Roadwork news (Kafka)",
                "EU legal documents (S3)",
            ],
        }
    )


@dataclass(frozen=True)
class ChartSpec:
    chart_id: str
    title: str
    subscribers: tuple[str, ...]
    renderer: Callable[..., None]


def _team_kpi_strip(
    sales: pd.DataFrame,
    inv: pd.DataFrame,
    company_valuation: pd.DataFrame,
    financial_postings: pd.DataFrame,
) -> None:
    st.subheader("Team KPI Strip")
    c1, c2, c3, c4, c5, c6 = st.columns(6)

    if sales.empty:
        c1.metric("Latest step", "n/a")
        c2.metric("Revenue", "n/a")
        c3.metric("Margin", "n/a")
    else:
        s = _safe_to_numeric(sales, ["NET_VALUE", "COST"])
        s["step_id"] = _step_id(s)
        step = int(s["step_id"].max())
        ss = s[s["step_id"] == step]
        c1.metric("Latest step", step)
        c2.metric("Revenue", f"{float(ss['NET_VALUE'].sum()):,.0f} EUR")
        c3.metric("Margin", f"{float((ss['NET_VALUE'] - ss['COST']).sum()):,.0f} EUR")

    stockouts = 0
    if not inv.empty and "STOCK" in inv.columns:
        ii = _safe_to_numeric(inv, ["STOCK"])
        stockouts = int((ii["STOCK"].fillna(0) <= 0).sum())
    c4.metric("Stockout items", stockouts)

    if company_valuation.empty:
        c5.metric("Cash", "n/a")
        c6.metric("Company valuation", "n/a")
    else:
        cv = _safe_to_numeric(company_valuation, ["BANK_CASH_ACCOUNT", "COMPANY_VALUATION"])
        row = cv.iloc[-1]
        c5.metric("Cash", f"{float(row.get('BANK_CASH_ACCOUNT', 0.0)):,.0f} EUR")
        c6.metric("Valuation", f"{float(row.get('COMPANY_VALUATION', 0.0)):,.0f} EUR")

    if not financial_postings.empty and "GL_ACCOUNT_NAME" in financial_postings.columns:
        fp = _safe_to_numeric(financial_postings, ["AMOUNT"])
        mask = fp["GL_ACCOUNT_NAME"].astype(str).str.contains("carbon", case=False, na=False)
        carbon = float(fp.loc[mask, "AMOUNT"].fillna(0.0).sum())
        st.caption(f"Carbon costs (observed): {carbon:,.0f} EUR")


def _execution_monitor_chart(purchase_orders: pd.DataFrame, production_orders: pd.DataFrame) -> None:
    st.subheader("Execution Monitor")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Purchase Orders Status**")
        if purchase_orders.empty:
            st.info("Keine Purchase-Order-Daten.")
        else:
            po = _safe_to_numeric(purchase_orders, ["QUANTITY"]).copy()
            po["status_norm"] = po.get("STATUS", "").astype(str).str.lower()
            po["lag_flag"] = np.where(
                po["status_norm"].str.contains("open|partial|late|delay", na=False),
                "LAGGING",
                "OK",
            )
            view = (
                po.groupby(["lag_flag", "MATERIAL_NUMBER", "MATERIAL_DESCRIPTION", "STATUS"], dropna=False)
                .agg(ordered_qty=("QUANTITY", "sum"))
                .reset_index()
                .sort_values(["lag_flag", "ordered_qty"], ascending=[False, False])
            )
            st.dataframe(view, use_container_width=True, hide_index=True)
    with c2:
        st.markdown("**Production Orders Progress**")
        if production_orders.empty:
            st.info("Keine Production-Order-Daten.")
        else:
            pr = _safe_to_numeric(production_orders, ["TARGET_QUANTITY", "CONFIRMED_QUANTITY"]).copy()
            pr["progress_pct"] = np.where(
                pr["TARGET_QUANTITY"] > 0,
                100.0 * pr["CONFIRMED_QUANTITY"] / pr["TARGET_QUANTITY"],
                0.0,
            )
            pr["lag_flag"] = np.where(pr["progress_pct"] < 95.0, "LAGGING", "OK")
            view = (
                pr.groupby(["lag_flag", "MATERIAL_NUMBER", "MATERIAL_DESCRIPTION"], dropna=False)
                .agg(target_qty=("TARGET_QUANTITY", "sum"), confirmed_qty=("CONFIRMED_QUANTITY", "sum"))
                .reset_index()
            )
            view["progress_pct"] = np.where(
                view["target_qty"] > 0,
                100.0 * view["confirmed_qty"] / view["target_qty"],
                0.0,
            )
            view = view.sort_values(["lag_flag", "progress_pct"], ascending=[False, True])
            st.dataframe(view, use_container_width=True, hide_index=True)


def _demand_heatmap_chart(market: pd.DataFrame, pricing: pd.DataFrame, key_suffix: str = "default") -> None:
    st.subheader("Demand Heatmap (Produkt x Region)")
    if market.empty:
        st.info("Keine Market-Daten.")
        return
    m = _safe_to_numeric(market, ["QUANTITY"]).copy()
    agg = (
        m.groupby(["MATERIAL_DESCRIPTION", "AREA"], dropna=False)["QUANTITY"]
        .sum()
        .reset_index()
        .rename(columns={"QUANTITY": "market_qty"})
    )
    if not pricing.empty:
        p = pricing[["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION"]].drop_duplicates()
        agg = agg.merge(p, on="MATERIAL_DESCRIPTION", how="left")
    fig = px.density_heatmap(
        agg,
        x="AREA",
        y="MATERIAL_DESCRIPTION",
        z="market_qty",
        color_continuous_scale="Blues",
    )
    st.plotly_chart(fig, use_container_width=True, key=f"demand_heatmap_{key_suffix}")
    st.dataframe(
        agg[["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION", "AREA", "market_qty"]]
        .sort_values(["market_qty"], ascending=False),
        use_container_width=True,
        hide_index=True,
    )


def _inventory_vs_demand_by_region_chart(
    inv: pd.DataFrame,
    market: pd.DataFrame,
    pricing: pd.DataFrame,
    current_game_rules: pd.DataFrame,
    key_suffix: str = "default",
) -> None:
    st.subheader("Inventory vs Demand by Region")
    if inv.empty or market.empty:
        st.info("Nicht genug Daten fuer Inventory-vs-Demand (Inventory/Market fehlt).")
        return

    # Map storage locations to area labels from game rules, with suffix fallback.
    loc_map: dict[str, str] = {}
    if not current_game_rules.empty:
        gr = current_game_rules.copy()
        mask = gr.get("ELEMENT", "").astype(str).eq("Storage_Location")
        for _, r in gr.loc[mask].iterrows():
            detail = str(r.get("DETAIL", "")).strip()
            value = str(r.get("VALUE", "")).strip()
            if detail and value:
                loc_map[detail] = value

    ii = _safe_to_numeric(inv, ["STOCK"]).copy()
    ii = ii[ii["MATERIAL_NUMBER"].astype(str).str.contains(r"-F\d+", regex=True, na=False)].copy()
    ii["area"] = ii["STORAGE_LOCATION"].astype(str).map(loc_map)
    missing = ii["area"].isna()
    ii.loc[missing, "area"] = np.where(
        ii.loc[missing, "STORAGE_LOCATION"].astype(str).str.endswith("N"),
        "North",
        np.where(
            ii.loc[missing, "STORAGE_LOCATION"].astype(str).str.endswith("S"),
            "South",
            np.where(ii.loc[missing, "STORAGE_LOCATION"].astype(str).str.endswith("W"), "West", "Unknown"),
        ),
    )
    inv_reg = (
        ii.groupby(["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION", "area"], dropna=False)["STOCK"]
        .sum()
        .reset_index()
        .rename(columns={"STOCK": "inventory_qty", "area": "AREA"})
    )

    mm = _safe_to_numeric(market, ["QUANTITY", "SIM_PERIOD"]).copy()
    mm["SIM_PERIOD"] = pd.to_numeric(mm.get("SIM_PERIOD"), errors="coerce").fillna(0).astype(int)
    max_period = int(mm["SIM_PERIOD"].max()) if not mm.empty else 0
    win = mm[mm["SIM_PERIOD"] >= (max_period - 2)].copy()
    if win.empty:
        win = mm.copy()
    dem_reg = (
        win.groupby(["MATERIAL_DESCRIPTION", "AREA"], dropna=False)["QUANTITY"]
        .sum()
        .reset_index()
        .rename(columns={"QUANTITY": "demand_qty_3p"})
    )

    if not pricing.empty:
        prod_map = (
            pricing[["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION"]]
            .dropna()
            .drop_duplicates(subset=["MATERIAL_DESCRIPTION"])
        )
        dem_reg = dem_reg.merge(prod_map, on="MATERIAL_DESCRIPTION", how="left")
    else:
        dem_reg["MATERIAL_NUMBER"] = None

    joined = dem_reg.merge(
        inv_reg[["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION", "AREA", "inventory_qty"]],
        on=["MATERIAL_NUMBER", "MATERIAL_DESCRIPTION", "AREA"],
        how="left",
    )
    joined["inventory_qty"] = joined["inventory_qty"].fillna(0.0)
    joined["gap_qty"] = joined["demand_qty_3p"] - joined["inventory_qty"]
    joined["status"] = np.where(joined["gap_qty"] > 0, "UNDERSTOCK", "COVERED")

    fig = px.density_heatmap(
        joined,
        x="AREA",
        y="MATERIAL_DESCRIPTION",
        z="gap_qty",
        color_continuous_scale="RdYlGn_r",
        title="Positive gap = Nachfrage > Bestand",
    )
    st.plotly_chart(fig, use_container_width=True, key=f"inventory_vs_demand_by_region_{key_suffix}")

    st.dataframe(
        joined[
            [
                "status",
                "MATERIAL_NUMBER",
                "MATERIAL_DESCRIPTION",
                "AREA",
                "inventory_qty",
                "demand_qty_3p",
                "gap_qty",
            ]
        ].sort_values(["status", "gap_qty"], ascending=[False, False]),
        use_container_width=True,
        hide_index=True,
    )


def _build_reco_bundle(
    sales: pd.DataFrame,
    market: pd.DataFrame,
    pricing: pd.DataFrame,
    inv: pd.DataFrame,
    suppliers: pd.DataFrame,
    indreq: pd.DataFrame,
    current_game_rules: pd.DataFrame,
    marketing_expenses: pd.DataFrame,
) -> dict[str, Any]:
    return {
        "price": build_price_suggestions(
            sales=sales,
            market=market,
            pricing=pricing,
            inventory=inv,
            price_step_eur=0.10,
            max_steps=5,
        ),
        "production": build_production_suggestions(
            sales=sales,
            inventory=inv,
            target_coverage_days=5,
        ),
        "procurement": build_procurement_suggestions(
            sales=sales,
            inventory=inv,
            suppliers=suppliers,
            independent_requirements=indreq,
            target_coverage_days=5,
        ),
        "transfer": build_transfer_suggestions(
            inventory=inv,
            market=market,
            current_game_rules=current_game_rules,
            co2e_penalty_eur_per_unit=0.02,
            demand_lookback_periods=3,
            target_coverage_periods=2,
        ),
        "advertising": build_advertising_suggestions(
            sales=sales,
            market=market,
            inventory=inv,
            marketing_expenses=marketing_expenses,
        ),
        "action_tips": build_action_tips(
            sales=sales,
            market=market,
            pricing=pricing,
            inventory=inv,
            suppliers=suppliers,
            independent_requirements=indreq,
            price_step_eur=0.10,
            max_price_steps=5,
            target_coverage_days=5,
        ),
    }


def _action_tips_chart(bundle: dict[str, Any]) -> None:
    st.subheader("Handlungsvorschlaege")
    tips: list[ActionTip] = bundle["action_tips"]
    if not tips:
        st.info("Keine Handlungsvorschlaege verfuegbar.")
        return
    st.dataframe(pd.DataFrame([t.__dict__ for t in tips]), use_container_width=True, hide_index=True)


def _price_urgency_chart(bundle: dict[str, Any]) -> None:
    st.subheader("Preis-Dringlichkeit (globales Pricing)")
    price_s: list[PriceSuggestion] = bundle["price"]
    if not price_s:
        st.info("Keine Preisvorschlaege verfuegbar.")
        return
    dfp = pd.DataFrame([s.__dict__ for s in price_s])
    dfp["price_delta"] = dfp["suggested_price"] - dfp["current_price"]
    dfp["urgent_flag"] = np.where(
        (dfp["price_delta"].abs() >= 0.30) | (dfp["inventory_units"].fillna(999999) <= 0),
        "URGENT",
        "monitor",
    )
    st.dataframe(
        dfp[
            [
                "urgent_flag",
                "material_number",
                "material_description",
                "distribution_channel",
                "current_price",
                "suggested_price",
                "price_delta",
                "reason",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


def _production_chart(bundle: dict[str, Any]) -> None:
    st.subheader("Produktion (CO41 / Planned orders)")
    prod_s: list[ProductionSuggestion] = bundle["production"]
    if not prod_s:
        st.info("Keine Produktionsvorschlaege verfuegbar.")
        return
    st.dataframe(pd.DataFrame([p.__dict__ for p in prod_s]), use_container_width=True, hide_index=True)


def _procurement_chart(bundle: dict[str, Any]) -> None:
    st.subheader("Einkauf (ZME12 / ME59N)")
    proc_s: list[ProcurementSuggestion] = bundle["procurement"]
    if not proc_s:
        st.info("Keine Einkaufsvorschlaege verfuegbar.")
        return
    st.dataframe(pd.DataFrame([p.__dict__ for p in proc_s]), use_container_width=True, hide_index=True)


def _advertising_chart(bundle: dict[str, Any]) -> None:
    st.subheader("Advertising Opportunity Matrix")
    ad_s: list[AdvertisingSuggestion] = bundle["advertising"]
    if not ad_s:
        st.info("Keine Advertising-Vorschlaege verfuegbar.")
        return
    dfa = pd.DataFrame([a.__dict__ for a in ad_s])
    st.dataframe(dfa, use_container_width=True, hide_index=True)


def _transfer_chart(bundle: dict[str, Any]) -> None:
    st.subheader("Transfer Board (Cost + CO2e)")
    tr_s: list[TransferSuggestion] = bundle["transfer"]
    if not tr_s:
        st.info("Keine Transfer-Vorschlaege verfuegbar.")
        return
    st.dataframe(pd.DataFrame([t.__dict__ for t in tr_s]), use_container_width=True, hide_index=True)


def _investments_chart(company_valuation: pd.DataFrame, financial_postings: pd.DataFrame) -> None:
    st.subheader("Investment Board")
    _investments(company_valuation=company_valuation, financial_postings=financial_postings)


def _chart_catalog() -> list[ChartSpec]:
    return [
        ChartSpec("team_kpis", "Team KPI Strip", ("Sales", "Production", "Procurement", "Steering"), _team_kpi_strip),
        ChartSpec("execution", "Execution Monitor", ("Production", "Procurement", "Steering"), _execution_monitor_chart),
        ChartSpec("actions", "Handlungsvorschlaege", ("Sales", "Production", "Procurement", "Steering"), _action_tips_chart),
        ChartSpec("price", "Preis-Dringlichkeit", ("Sales", "Steering"), _price_urgency_chart),
        ChartSpec("demand_heatmap", "Demand Heatmap", ("Sales", "Production", "Steering"), _demand_heatmap_chart),
        ChartSpec(
            "inventory_vs_demand",
            "Inventory vs Demand by Region",
            ("Production", "Steering"),
            _inventory_vs_demand_by_region_chart,
        ),
        ChartSpec("production", "Produktion", ("Production", "Steering"), _production_chart),
        ChartSpec("procurement", "Einkauf", ("Procurement", "Production"), _procurement_chart),
        ChartSpec("advertising", "Advertising Matrix", ("Sales", "Steering"), _advertising_chart),
        ChartSpec("transfer", "Transfer Board", ("Steering", "Production"), _transfer_chart),
        ChartSpec("investments", "Investment Board", ("Steering", "Sales"), _investments_chart),
    ]


def main() -> None:
    st.set_page_config(page_title="ERPsim Workbench Dashboard", layout="wide")
    cfg = AppConfig()

    with st.sidebar:
        st.subheader("Live update")
        st.caption("Dieses Dashboard führt keine Fetch-Aktionen aus.")
        st.caption("Starte die Ingestion separat: python automation/fetch_pipeline.py --interval-seconds 30")

    # Auto-refresh (UI stays responsive as long as the script rerun is fast).
    st_autorefresh(interval=int(cfg.auto_refresh_seconds * 1000), key="wb_autorefresh")

    snap = load_latest_snapshots(cfg.data_dir)
    _render_header(snap)

    frames = _load_frames_fast(snap)
    sales = frames.get("sales", pd.DataFrame())
    market = frames.get("market", pd.DataFrame())
    inv = frames.get("current_inventory", pd.DataFrame())
    pricing = frames.get("pricing_conditions", pd.DataFrame())
    suppliers = frames.get("current_suppliers_prices", pd.DataFrame())
    indreq = frames.get("independent_requirements", pd.DataFrame())
    purchase_orders = frames.get("purchase_orders", pd.DataFrame())
    production_orders = frames.get("production_orders", pd.DataFrame())
    production = frames.get("production", pd.DataFrame())
    marketing_expenses = frames.get("marketing_expenses", pd.DataFrame())
    financial_postings = frames.get("financial_postings", pd.DataFrame())
    company_valuation = frames.get("company_valuation", pd.DataFrame())
    current_game_rules = frames.get("current_game_rules", pd.DataFrame())

    if cfg.persist_ingested_snapshots:
        # Only ingest when a *new* snapshot appears (avoid doing work on every refresh).
        latest_stamp = None
        if snap.sales_path:
            latest_stamp = Path(snap.sales_path).name.split("_")[0:2]
            latest_stamp = "_".join(latest_stamp) if len(latest_stamp) == 2 else None
        last_ingested = st.session_state.get("last_ingested_stamp")

        if latest_stamp and latest_stamp != last_ingested:
            try:
                ingestion_id = ingest_latest_snapshots_to_duckdb(
                    snap=snap,
                    db_path=cfg.duckdb_path,
                    note="workbench dashboard auto-ingest",
                )
                st.session_state["last_ingested_stamp"] = latest_stamp
                st.caption(
                    f"Persisted snapshots to DuckDB lake: {cfg.duckdb_path} "
                    f"(ingestion_id={ingestion_id}, snapshot={latest_stamp})"
                )
            except Exception as exc:
                st.warning(f"DuckDB lake ingest skipped due to error: {exc}")

    st.info("Chart-Pool aktiv: alle Kennzahlen werden zentral berechnet und per Subscriber in Player-Tabs angezeigt.")
    _disruptor_placeholder()
    st.divider()

    bundle = _build_reco_bundle(
        sales=sales,
        market=market,
        pricing=pricing,
        inv=inv,
        suppliers=suppliers,
        indreq=indreq,
        current_game_rules=current_game_rules,
        marketing_expenses=marketing_expenses,
    )
    catalog = _chart_catalog()
    tab_names = ["Sales", "Production", "Procurement", "Steering"]
    tabs = st.tabs(tab_names)

    for i, tab_name in enumerate(tab_names):
        with tabs[i]:
            st.caption(f"Subscriber view: {tab_name}")
            for spec in catalog:
                if tab_name not in spec.subscribers:
                    continue
                if spec.chart_id == "team_kpis":
                    spec.renderer(sales, inv, company_valuation, financial_postings)
                elif spec.chart_id == "execution":
                    spec.renderer(purchase_orders, production_orders)
                elif spec.chart_id == "demand_heatmap":
                    spec.renderer(market, pricing, f"{tab_name}_{spec.chart_id}")
                elif spec.chart_id == "inventory_vs_demand":
                    spec.renderer(inv, market, pricing, current_game_rules, f"{tab_name}_{spec.chart_id}")
                elif spec.chart_id == "investments":
                    spec.renderer(company_valuation, financial_postings)
                else:
                    spec.renderer(bundle)
                st.divider()

    st.caption(f"Auto-refresh: {cfg.auto_refresh_seconds}s | Rendered at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()

