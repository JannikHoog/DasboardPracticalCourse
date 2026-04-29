from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from odata_client import build_odata_config, fetch_all, load_config, save_snapshots


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_once(config_path: Path, state_path: Path) -> Dict[str, Any]:
    raw = load_config(config_path)
    team_code = raw.get("team_code", "UNKNOWN")
    odata_cfg = build_odata_config(raw)

    started = time.time()
    frames = fetch_all(odata_cfg)
    if frames:
        save_snapshots(frames, odata_cfg.data_dir)

    elapsed = round(time.time() - started, 3)
    summary = {
        "team_code": team_code,
        "timestamp_utc": _utc_now(),
        "elapsed_seconds": elapsed,
        "feeds_total": len(odata_cfg.feeds),
        "feeds_fetched": len(frames),
        "rows_by_feed": {k: int(len(v)) for k, v in frames.items()},
    }
    _write_json(state_path, summary)
    print(
        f"[pipeline] fetched={summary['feeds_fetched']} "
        f"elapsed={summary['elapsed_seconds']}s team={team_code}"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only ingestion pipeline (continuous snapshot collector)."
    )
    parser.add_argument("--config", default="automation/config.json")
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument(
        "--state-file",
        default="automation/pipeline_state.json",
        help="Pipeline heartbeat/state output file",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    state_path = Path(args.state_file)
    interval_seconds = max(5, int(args.interval_seconds))

    if args.once:
        run_once(config_path, state_path)
        return

    print(
        "[pipeline] starting continuous read-only ingestion "
        f"(interval={interval_seconds}s, config={config_path})"
    )
    while True:
        try:
            run_once(config_path, state_path)
        except Exception as exc:
            _write_json(
                state_path,
                {
                    "timestamp_utc": _utc_now(),
                    "status": "error",
                    "error": str(exc),
                },
            )
            print(f"[pipeline] error: {exc}")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()

