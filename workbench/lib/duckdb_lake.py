from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

import duckdb

from workbench.lib.loaders import LatestSnapshots


def _is_probably_valid_csv(csv_path: Path) -> bool:
    """
    Guard against zero-byte / headerless files.
    Some ERPsim feeds can legitimately return 0 rows; our snapshot writer may still
    emit an empty file. DuckDB can't safely infer schema from that.
    """
    try:
        if csv_path.stat().st_size < 5:
            return False
        head = csv_path.read_bytes()[:2048]
        # Heuristic: expect at least one delimiter in header line
        return b"," in head
    except Exception:
        return False


def _connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute("PRAGMA threads=4;")
    return con


def _init(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS lake_ingestions (
          ingestion_id VARCHAR PRIMARY KEY,
          ingested_at_utc TIMESTAMP,
          data_dir VARCHAR,
          note VARCHAR
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS lake_sources (
          ingestion_id VARCHAR,
          dataset VARCHAR,
          source_path VARCHAR,
          PRIMARY KEY (ingestion_id, dataset)
        );
        """
    )


def _register_sources(con: duckdb.DuckDBPyConnection, ingestion_id: str, snap: LatestSnapshots) -> None:
    srcs = {}
    for k, v in asdict(snap).items():
        if k.endswith("_path"):
            srcs[k] = str(v) if v else None

    mapping = {
        "sales": snap.sales_path,
        "market": snap.market_path,
        "current_inventory": snap.current_inventory_path,
        "current_inventory_kpi": snap.current_inventory_kpi_path,
        "pricing_conditions": snap.pricing_conditions_path,
        "current_suppliers_prices": snap.current_suppliers_prices_path,
        "independent_requirements": snap.independent_requirements_path,
        "production_orders": snap.production_orders_path,
        "financial_postings": getattr(snap, "financial_postings_path", None),
        "company_valuation": getattr(snap, "company_valuation_path", None),
        "current_game_rules": getattr(snap, "current_game_rules_path", None),
    }
    for dataset, path in mapping.items():
        if not path:
            continue
        con.execute(
            "INSERT OR REPLACE INTO lake_sources (ingestion_id, dataset, source_path) VALUES (?, ?, ?)",
            [ingestion_id, dataset, str(path)],
        )


def _ingest_csv(
    con: duckdb.DuckDBPyConnection,
    *,
    ingestion_id: str,
    dataset: str,
    csv_path: Path,
) -> None:
    table = f"bronze_{dataset}"

    if not _is_probably_valid_csv(csv_path):
        # Skip empty/headerless snapshots (common when feed has 0 rows).
        return

    # Create the table on first ingest from the CSV schema; always append afterwards.
    try:
        con.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} AS
            SELECT
              *,
              ?::VARCHAR AS ingestion_id,
              now()::TIMESTAMP AS ingested_at_utc,
              ?::VARCHAR AS source_path
            FROM read_csv_auto(?, ALL_VARCHAR=TRUE);
            """,
            [ingestion_id, str(csv_path), str(csv_path)],
        )

        con.execute(
            f"""
            INSERT INTO {table}
            SELECT
              *,
              ?::VARCHAR AS ingestion_id,
              now()::TIMESTAMP AS ingested_at_utc,
              ?::VARCHAR AS source_path
            FROM read_csv_auto(?, ALL_VARCHAR=TRUE);
            """,
            [ingestion_id, str(csv_path), str(csv_path)],
        )
    except Exception:
        # Persistence must never break the dashboard. If schema inference fails, skip this dataset.
        return


def ingest_latest_snapshots_to_duckdb(
    *,
    snap: LatestSnapshots,
    db_path: Path,
    note: str | None = None,
) -> str:
    """
    Append-only ingestion of the *latest* snapshot CSVs into a DuckDB file.

    - Each ingestion gets a unique `ingestion_id` and `ingested_at_utc`.
    - Each dataset is stored as `bronze_<dataset>` with *all columns as VARCHAR* to avoid schema drift issues.
      (We can materialize typed silver tables later.)
    """
    ingested_at = datetime.utcnow()
    ingestion_id = ingested_at.strftime("%Y%m%dT%H%M%SZ")
    note = note or ""

    con = _connect(Path(db_path))
    try:
        _init(con)
        con.execute(
            "INSERT OR REPLACE INTO lake_ingestions (ingestion_id, ingested_at_utc, data_dir, note) VALUES (?, ?, ?, ?)",
            [ingestion_id, ingested_at, str(snap.data_dir), note],
        )
        _register_sources(con, ingestion_id, snap)

        mapping = {
            "sales": snap.sales_path,
            "market": snap.market_path,
            "current_inventory": snap.current_inventory_path,
            "current_inventory_kpi": snap.current_inventory_kpi_path,
            "pricing_conditions": snap.pricing_conditions_path,
            "current_suppliers_prices": snap.current_suppliers_prices_path,
            "independent_requirements": snap.independent_requirements_path,
            "production_orders": snap.production_orders_path,
            "financial_postings": getattr(snap, "financial_postings_path", None),
            "company_valuation": getattr(snap, "company_valuation_path", None),
            "current_game_rules": getattr(snap, "current_game_rules_path", None),
        }

        for dataset, path in mapping.items():
            if not path or not Path(path).exists():
                continue
            _ingest_csv(con, ingestion_id=ingestion_id, dataset=dataset, csv_path=Path(path))

        con.commit()
        return ingestion_id
    finally:
        con.close()

