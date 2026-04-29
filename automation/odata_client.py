from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Union

import pandas as pd
import requests


@dataclass
class ODataConfig:
    timeout_seconds: int
    verify_tls: bool
    base_url: str
    username: str
    password: str
    entities: list[str]
    feeds: Dict[str, str]
    data_dir: Path


def load_config(config_path: Union[str, Path]) -> Dict[str, Any]:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_odata_config(raw: Dict[str, Any]) -> ODataConfig:
    odata_raw = raw["odata"]
    base_url = odata_raw.get("base_url", "").strip().rstrip("/")
    entities = odata_raw.get("entities", [])
    username = odata_raw.get("username", "") or raw.get("fiori", {}).get("username", "")
    password = odata_raw.get("password", "") or raw.get("fiori", {}).get("password", "")

    return ODataConfig(
        timeout_seconds=odata_raw["timeout_seconds"],
        verify_tls=odata_raw["verify_tls"],
        base_url=base_url,
        username=username,
        password=password,
        entities=entities,
        feeds=odata_raw["feeds"],
        data_dir=Path(raw["output"]["data_dir"]),
    )


def _extract_rows(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    # Handles common OData v2/v4 response shapes.
    if "value" in payload and isinstance(payload["value"], list):
        return payload["value"]
    if "d" in payload and isinstance(payload["d"], dict) and "results" in payload["d"]:
        return payload["d"]["results"]
    raise ValueError("Unsupported OData payload shape.")


def fetch_feed(name: str, url: str, cfg: ODataConfig) -> pd.DataFrame:
    if not url:
        raise ValueError(f"Feed URL for '{name}' is empty in config.")

    resp = requests.get(
        url,
        timeout=cfg.timeout_seconds,
        verify=cfg.verify_tls,
        headers={"Accept": "application/json"},
        auth=(cfg.username, cfg.password) if cfg.username else None,
    )
    resp.raise_for_status()
    payload = resp.json()
    rows = _extract_rows(payload)
    return pd.DataFrame(rows)


def fetch_all(cfg: ODataConfig) -> Dict[str, pd.DataFrame]:
    feed_map: Dict[str, str] = dict(cfg.feeds)

    # If explicit feeds are missing, auto-build from base_url + entities.
    if not feed_map and cfg.base_url and cfg.entities:
        feed_map = {
            entity.lower(): f"{cfg.base_url}/{entity}?$format=json" for entity in cfg.entities
        }

    result: Dict[str, pd.DataFrame] = {}
    valid_feeds = {name: url for name, url in feed_map.items() if url}
    if not valid_feeds:
        return result

    # Parallel fetching keeps ingestion cycle short and independent from slow feeds.
    max_workers = min(8, max(1, len(valid_feeds)))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {
            ex.submit(fetch_feed, name, url, cfg): name for name, url in valid_feeds.items()
        }
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                result[name] = fut.result()
            except Exception as exc:
                # Keep pipeline resilient: one broken feed must not block all others.
                print(f"[odata] warning: failed feed '{name}': {exc}")
                result[name] = pd.DataFrame()
    return result


def save_snapshots(frames: Dict[str, pd.DataFrame], data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for name, frame in frames.items():
        out = data_dir / f"{stamp}_{name}.csv"
        frame.to_csv(out, index=False)
        print(f"[odata] wrote {out} ({len(frame)} rows)")
