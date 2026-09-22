"""ONE URL FOR EVERYTHING CHATGPT OWES THE PIPELINE — `exchange/OPEN.json`.

Operator, 2026-09-22: *"I should not have to paste anything in a ChatGPT.
ChatGPT should be reading the instructions somewhere on the GitHub that you
can update at will."* The instructions live in `doctor/PROMPTS.md` (section
7, the mailbox round), read fresh from `main` at every firing. This file is
the one index that section opens: the three mailboxes (reviews, asks,
rewrites) each keep their own `OPEN.json`; this rolls them into one, so a
task never has to know how many mailboxes exist. Refreshed by every mailbox
whenever its own index changes. Best-effort: a failed refresh is a stale
count, never a crashed run.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAILBOXES = ("reviews", "asks", "rewrites")


def refresh(exchange_dir: Path | None = None) -> Path | None:
    exchange_dir = Path(exchange_dir or REPO / "exchange")
    try:
        boxes = {}
        total = 0
        for name in MAILBOXES:
            ip = exchange_dir / name / "OPEN.json"
            n = 0
            if ip.exists():
                try:
                    n = len(json.loads(ip.read_text()).get("open") or [])
                except Exception:  # noqa: BLE001
                    n = 0
            boxes[name] = {"open": n, "index": f"exchange/{name}/OPEN.json"}
            total += n
        out = {
            "schema": "shorts-exchange-index/v1",
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open_total": total,
            "mailboxes": boxes,
            "how": ("The contract is doctor/PROMPTS.md section 7 (the mailbox "
                    "round). Open each mailbox's `index` that has open > 0 and "
                    "do exactly what its entries say. If open_total is 0, "
                    "there is nothing to do."),
        }
        exchange_dir.mkdir(parents=True, exist_ok=True)
        p = exchange_dir / "OPEN.json"
        p.write_text(json.dumps(out, indent=1) + "\n")
        return p
    except Exception:  # noqa: BLE001
        return None
