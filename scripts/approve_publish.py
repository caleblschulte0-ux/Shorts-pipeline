#!/usr/bin/env python3
"""Owner approval bound to the EXACT package (PR#173 adoption: approval_token).

``python3 scripts/approve_publish.py <slug>`` writes
``output/curiosity_<slug>.approval.json`` containing the sha256 of the
package manifest at approval time. The publish path requires this approval
for a real upload and verifies TWO things at upload time:

  1. the approval's manifest hash equals the CURRENT manifest's hash, and
  2. the manifest still verifies against the artifacts on disk.

So an approval is a statement about one exact cut: any re-render, any
artifact swap, or any manifest edit makes it inert — an approval can never
be reused on a different film. Revoke with --revoke.

This composes with (never replaces) the other publish guards: the quality
gates, CURIOSITY_PUBLISH_ENABLED, and the kill switch file
``state/curiosity_kill_switch`` (its mere existence halts all uploads).
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

KILL_SWITCH = REPO / "state" / "curiosity_kill_switch"


def approval_path(out: Path) -> Path:
    return out.with_suffix(".approval.json")


def approve(out: Path) -> Path:
    """Write an approval bound to the current manifest. Refuses when there is
    no manifest, the manifest does not verify, or the producer's own report
    says quarantine — an owner cannot approve an unproven package."""
    import artifact_identity as ai
    m = ai.load_manifest(out)
    if m is None:
        raise SystemExit(f"REFUSED: no package manifest for {out} — produce it first")
    ok, reasons = ai.verify_manifest(out)
    if not ok:
        raise SystemExit("REFUSED: package does not match its manifest: "
                         + "; ".join(reasons[:3]))
    pkg = out.with_name(out.stem + "_pkg")
    report = {}
    try:
        report = json.loads((pkg / "produce_report.json").read_text())
    except (OSError, json.JSONDecodeError):
        raise SystemExit("REFUSED: no produce_report.json — run the producer")
    if report.get("status") != "pass":
        raise SystemExit("REFUSED: producer verdict is "
                         f"{report.get('status')!r} ({'; '.join(report.get('reasons', [])[:2])}) "
                         "— a quarantined film cannot be approved")
    doc = {
        "slug": m.get("slug"),
        "manifest_sha256": m.get("manifest_sha256"),
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "approved_by": getpass.getuser(),
    }
    dest = approval_path(out)
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n")
    tmp.replace(dest)
    return dest


def check_approval(out: Path) -> tuple[bool, str]:
    """(approved, reason). Fail closed on anything unexpected."""
    import artifact_identity as ai
    ap = approval_path(out)
    if not ap.exists():
        return False, (f"no owner approval ({ap.name}) — run "
                       f"scripts/approve_publish.py for this exact cut")
    try:
        doc = json.loads(ap.read_text())
    except (OSError, json.JSONDecodeError):
        return False, "approval file unreadable"
    m = ai.load_manifest(out)
    if m is None:
        return False, "approval exists but the package has no manifest"
    if doc.get("manifest_sha256") != m.get("manifest_sha256"):
        return False, ("approval is bound to a DIFFERENT package "
                       f"({str(doc.get('manifest_sha256'))[:12]}… != current "
                       f"{str(m.get('manifest_sha256'))[:12]}…) — re-approve "
                       "the current cut")
    ok, reasons = ai.verify_manifest(out)
    if not ok:
        return False, ("package changed since its manifest: "
                       + "; ".join(reasons[:2]))
    return True, f"approved by {doc.get('approved_by')} at {doc.get('approved_at')}"


def kill_switch_engaged() -> str | None:
    """Non-None (with the reason) when the hard stop file exists. The kill
    switch outranks every flag, approval, and --force."""
    if KILL_SWITCH.exists():
        try:
            first = KILL_SWITCH.read_text().strip().splitlines()
            note = first[0] if first else ""
        except OSError:
            note = ""
        return ("KILL SWITCH engaged (state/curiosity_kill_switch exists"
                + (f": {note}" if note else "") + ") — all uploads halted")
    return None


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--revoke", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    out = a.out or (REPO / "output" / f"curiosity_{a.slug}.mp4")
    if a.revoke:
        approval_path(out).unlink(missing_ok=True)
        print(f"approval revoked for {a.slug}")
        return 0
    if a.check:
        ok, why = check_approval(out)
        print(("APPROVED: " if ok else "NOT APPROVED: ") + why)
        return 0 if ok else 1
    dest = approve(out)
    print(f"APPROVED {a.slug} — bound to manifest "
          f"{json.loads(dest.read_text())['manifest_sha256'][:16]}… -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
