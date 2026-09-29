"""Has TikTok audited the Shorts Media app for PUBLIC Direct Post?

TikTok answers at the first step of a post: `video/init` with
privacy_level=PUBLIC_TO_EVERYONE is refused with
`unaudited_client_can_only_post_to_private_accounts` until the audit passes.
This asks exactly that and then STOPS: the video bytes are never sent, so
nothing is published (the unused upload slot expires on TikTok's side).

Publishes nothing, so it needs no quality gate. Runs only in GitHub Actions
on main (tiktok_audit_probe.yml) — the site gives tokens to nothing else.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.uploaders import CREATOR_INFO_URL, TikTokUploader  # noqa: E402

SIZE = 5_000_000  # a plausible single-chunk short; never actually sent


def probe(token: str) -> tuple[str, str]:
    """-> (verdict, detail): verdict is 'audited', 'unaudited' or 'unknown'."""
    import requests
    h = {"Authorization": f"Bearer {token}",
         "Content-Type": "application/json; charset=UTF-8"}
    ci = requests.post(CREATOR_INFO_URL, headers=h, json={}, timeout=30).json()
    opts = (ci.get("data") or {}).get("privacy_level_options") or []
    r = requests.post(TikTokUploader.INIT_URL, headers=h, timeout=30, json={
        "post_info": {"title": "audit probe (never uploaded)",
                      "privacy_level": "PUBLIC_TO_EVERYONE"},
        "source_info": {"source": "FILE_UPLOAD", "video_size": SIZE,
                        "chunk_size": SIZE, "total_chunk_count": 1}})
    body = r.text
    if r.ok and '"publish_id"' in body:
        return "audited", f"privacy options {opts}; public init accepted"
    if "unaudited_client" in body:
        return "unaudited", f"privacy options {opts}; TikTok: {body}"
    return "unknown", f"privacy options {opts}; HTTP {r.status_code}: {body}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--handle", required=True)
    handle = ap.parse_args().handle.strip().lstrip("@")
    os.environ["TIKTOK_HANDLE_PROBE"] = handle
    verdict, detail = probe(TikTokUploader(channel="probe")._token())
    words = {
        "audited": "APPROVED for public posting — nothing to apply for.",
        "unaudited": ("NOT yet audited — TikTok will keep API posts private "
                      "(Only me). Apply for the Direct Post audit on the "
                      "Content Posting API page of the developer portal."),
        "unknown": "TikTok gave an unexpected answer — see detail.",
    }[verdict]
    out = (f"TikTok Direct Post audit probe via @{handle} (nothing published)\n"
           f"- VERDICT: {words}\n- detail: {detail}\n")
    print(out)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(out)
    return 0 if verdict != "unknown" else 1


if __name__ == "__main__":
    sys.exit(main())
