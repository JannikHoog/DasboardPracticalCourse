from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import pandas as pd


_STAMP_RE = re.compile(r"(?P<stamp>\d{8}_\d{6})_(?P<name>.+)\.csv$", re.IGNORECASE)


def _latest_file(data_dir: Path, suffix: str) -> Path | None:
    # Example: 20260427_110202_sales.csv
    files = sorted(data_dir.glob(f"*_{suffix}.csv"))
    return files[-1] if files else None


@dataclass(frozen=True)
class LatestSnapshots:
    data_dir: Path

    sales_path: Path | None
    market_path: Path | None
    current_inventory_path: Path | None
    current_inventory_kpi_path: Path | None
    pricing_conditions_path: Path | None
    current_suppliers_prices_path: Path | None
    independent_requirements_path: Path | None
    production_orders_path: Path | None
    purchase_orders_path: Path | None
    production_path: Path | None
    stock_transfers_path: Path | None
    marketing_expenses_path: Path | None
    financial_postings_path: Path | None
    company_valuation_path: Path | None
    current_game_rules_path: Path | None

    def load_frames(self) -> dict[str, pd.DataFrame]:
        frames: dict[str, pd.DataFrame] = {}
        mapping = {
            "sales": self.sales_path,
            "market": self.market_path,
            "current_inventory": self.current_inventory_path,
            "current_inventory_kpi": self.current_inventory_kpi_path,
            "pricing_conditions": self.pricing_conditions_path,
            "current_suppliers_prices": self.current_suppliers_prices_path,
            "independent_requirements": self.independent_requirements_path,
            "production_orders": self.production_orders_path,
            "purchase_orders": self.purchase_orders_path,
            "production": self.production_path,
            "stock_transfers": self.stock_transfers_path,
            "marketing_expenses": self.marketing_expenses_path,
            "financial_postings": self.financial_postings_path,
            "company_valuation": self.company_valuation_path,
            "current_game_rules": self.current_game_rules_path,
        }

        for key, path in mapping.items():
            if not path or not path.exists():
                frames[key] = pd.DataFrame()
                continue
            try:
                frames[key] = pd.read_csv(path)
            except Exception:
                frames[key] = pd.DataFrame()
        return frames


def load_latest_snapshots(data_dir: Path) -> LatestSnapshots:
    data_dir = Path(data_dir)
    return LatestSnapshots(
        data_dir=data_dir,
        sales_path=_latest_file(data_dir, "sales"),
        market_path=_latest_file(data_dir, "market"),
        current_inventory_path=_latest_file(data_dir, "current_inventory"),
        current_inventory_kpi_path=_latest_file(data_dir, "current_inventory_kpi"),
        pricing_conditions_path=_latest_file(data_dir, "pricing_conditions"),
        current_suppliers_prices_path=_latest_file(data_dir, "current_suppliers_prices"),
        independent_requirements_path=_latest_file(data_dir, "independent_requirements"),
        production_orders_path=_latest_file(data_dir, "production_orders"),
        purchase_orders_path=_latest_file(data_dir, "purchase_orders"),
        production_path=_latest_file(data_dir, "production"),
        stock_transfers_path=_latest_file(data_dir, "stock_transfers"),
        marketing_expenses_path=_latest_file(data_dir, "marketing_expenses"),
        financial_postings_path=_latest_file(data_dir, "financial_postings"),
        company_valuation_path=_latest_file(data_dir, "company_valuation"),
        current_game_rules_path=_latest_file(data_dir, "current_game_rules"),
    )

