from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Any

from odata_client import load_config, build_odata_config, fetch_all, save_snapshots


def _load_runtime_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Config not found: {path}. Copy automation/config.example.json to automation/config.json first."
        )
    return load_config(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fetch", "execute"], required=True)
    parser.add_argument(
        "--config", default="automation/config.json", help="Path to runtime config JSON"
    )
    args = parser.parse_args()

    raw = _load_runtime_config(Path(args.config))
    team_code = raw.get("team_code", "CC")
    print(f"[info] team_code={team_code}")

    if args.mode == "fetch":
        odata_cfg = build_odata_config(raw)
        frames = fetch_all(odata_cfg)
        if not frames:
            print("[odata] no feeds configured; nothing to fetch.")
            return
        save_snapshots(frames, odata_cfg.data_dir)
        return

    if args.mode == "execute":
        raise RuntimeError(
            "Reads-only policy is active: UI execution is disabled in this workspace. "
            "Use --mode fetch to read OData snapshots."
        )


if __name__ == "__main__":
    main()
