#!/usr/bin/env python3
"""Sports runner adapter: preserve no-judge renders for the ChatGPT mailbox.

The sports capture runner predates the review mailbox. Its showrunner context
therefore never opened the mailbox, so a Claude quota + Gemini 429 held every
cut and then discarded the only copy ChatGPT could have graded. This adapter
changes only that handoff: the existing sports discovery/render/upload logic
stays in scripts.run_sports, the shared fail-closed gate stays sovereign, and
code still decides every mailbox verdict.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_sports as sports  # noqa: E402
from shared import showrunner_gate  # noqa: E402


def _mailbox_package(c: dict, meta: dict, slug: str) -> str:
    """Persist the upload metadata claim_reviews needs after this runner dies."""
    topic = sports.permalink_key(c)
    key = hashlib.sha1(topic.encode("utf-8")).hexdigest()[:10]
    safe = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-")[:48] or "clip"
    rel = Path("exchange") / "reviews" / "sports_packages" / f"{safe}__{key}.json"
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)

    body = "\n\n".join(
        x.strip() for x in (str(meta.get("caption") or ""), str(meta.get("cta") or ""))
        if x.strip()
    )
    source = f"Via r/{c.get('sub')}: {topic}" if c.get("sub") else topic
    pkg = {
        "format": sports.FORMAT,
        "channel": "",
        "title": str(meta.get("title") or "")[:100],
        "topic": topic,
        "text": body or str(c.get("post_title") or ""),
        "source": source,
        "hashtags": sports.tags(meta, c),
    }
    path.write_text(json.dumps(pkg, indent=2, ensure_ascii=False) + "\n")
    return rel.as_posix()


def judge(mp4: Path, c: dict, meta: dict, hook: str, *, will_upload: bool) -> dict:
    """Same sports gate, with the existing judge-of-last-resort mailbox opened."""
    slug = sports.rt._slug(
        f"sports {c.get('who')} {sports.permalink_key(c)[-12:]}"
    )
    ctx = {
        "slug": slug,
        "title": meta.get("title"),
        "hook": hook,
        "format": sports.FORMAT,
        "topic": sports.permalink_key(c),
        "segments": [c.get("post_title"), meta.get("caption")],
    }
    if will_upload:
        # showrunner_review files a request only when this marker exists.
        # The package sidecar lets the existing trending claim path recreate
        # the Sports upload later without inventing metadata from memory.
        ctx["package"] = _mailbox_package(c, meta, slug)
        ctx["mailbox"] = {"channel": sports.CHANNEL}

    gate = showrunner_gate.run(
        mp4, slug=slug, context=ctx, will_upload=will_upload
    )
    showrunner_gate.log(gate, slug)
    return gate


def main() -> int:
    sports.judge = judge
    return sports.main()


if __name__ == "__main__":
    sys.exit(main())
