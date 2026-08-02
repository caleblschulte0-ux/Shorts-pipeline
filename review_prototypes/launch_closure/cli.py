from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from .closure import run_launch_rehearsal


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated production-shaped launch rehearsal.")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="shorts-launch-") as temp_dir:
        payload = run_launch_rehearsal(Path(temp_dir), args.out)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0 if payload["report"]["closed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
