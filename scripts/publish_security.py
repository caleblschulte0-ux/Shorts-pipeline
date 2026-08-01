#!/usr/bin/env python3
"""PUBLISH SECURITY SCAN — the nextgen leak scanner on the REAL upload payload.

Adapter over experiments/curiosity_nextgen/security_scanner.py: before any
upload, the EXACT outbound payload (title, description, tags, localizations,
caption text, public metadata) is scanned recursively for

  BLOCKING  — secrets / API keys / private keys / bearer tokens, credential-
              named fields, internal-instruction fields (planner reasoning,
              system prompts, hidden rubrics) that must never ship publicly;
  WARNING   — emails, phone numbers, off-allowlist URLs (reported, logged,
              but not by themselves a refusal — source citations legitimately
              carry URLs and contact lines).

FAIL-CLOSED CONTRACT: any BLOCKING finding refuses the upload, and a scanner
error also refuses (an unscanned payload never ships). --force never bypasses
this — it is a legal/technical gate, not scheduling. The report is written to
``output/curiosity_<slug>.security.json`` either way so every decision is
auditable from artifacts.

    python3 scripts/publish_security.py <slug>     # scan the packaged story
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts", REPO / "experiments"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from curiosity_nextgen.security_scanner import (   # noqa: E402
    FindingSeverity, scan_payload)


def build_public_payload(out: Path, title: str = "", description: str = "",
                         tags: list[str] | None = None,
                         localizations: dict | None = None) -> dict:
    """Everything that leaves the machine on an upload, assembled from the
    real sidecars. Only PUBLIC-bound fields — internal reports stay internal
    and are not the scanner's concern here."""
    payload: dict = {
        "title": title,
        "description": description,
        "tags": list(tags or []),
        "localizations": localizations or {},
    }
    meta_path = out.with_suffix(".meta.json")
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except (OSError, json.JSONDecodeError):
            meta = {"_unreadable": str(meta_path)}
        # the WHOLE meta sidecar is scanned, not just the fields the current
        # description template reads: anything in it can feed public text via
        # a future template change, so an internal-instruction or credential
        # field in meta.json blocks now, before it ever leaks
        payload["meta"] = meta
    srt = out.with_suffix(".srt")
    if srt.exists():
        try:
            payload["captions"] = srt.read_text()[:200_000]
        except OSError:
            payload["captions"] = ""
    return payload


def scan_upload(out: Path, title: str = "", description: str = "",
                tags: list[str] | None = None,
                localizations: dict | None = None) -> tuple[bool, list[str]]:
    """(ok, reasons). ok=False on ANY blocking finding or scanner failure.
    Writes the machine-readable report next to the video regardless."""
    report_path = out.with_suffix(".security.json")
    try:
        payload = build_public_payload(out, title, description, tags,
                                       localizations)
        rep = scan_payload(payload)
        doc = {
            "video": out.name,
            "valid": rep.valid,
            "blocking_paths": list(rep.blocking_paths),
            "findings": [
                {"path": f.path, "kind": f.kind.value,
                 "severity": f.severity.value, "excerpt": f.excerpt[:60]}
                for f in rep.findings],
            "warnings": sum(1 for f in rep.findings
                            if f.severity is FindingSeverity.WARNING),
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(doc, indent=2) + "\n")
        if not rep.valid:
            kinds = sorted({f.kind.value for f in rep.findings
                            if f.severity is FindingSeverity.BLOCKING})
            return False, [
                "security scan BLOCKING: "
                f"{', '.join(kinds)} at {', '.join(rep.blocking_paths[:4])}"
                f" — see {report_path.name}"]
        return True, []
    except Exception as e:  # noqa: BLE001 — an unscanned payload never ships
        return False, [f"security scan could not run ({str(e)[:80]}) — "
                       "refusing to publish an unscanned payload"]


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    out = a.out or (REPO / "output" / f"curiosity_{a.slug}.mp4")
    # standalone mode reconstructs the public text from the config + sidecars
    title, desc, tags = a.slug, "", []
    try:
        cfg = json.loads((REPO / "data_learning" /
                          "curiosity.config.json").read_text())
        sc = next((s for s in cfg.get("stories", [])
                   if s.get("slug") == a.slug), {})
        title = sc.get("title", a.slug)
        desc = " ".join(str(sc.get(k, "")) for k in ("hook", "description"))
        tags = list(sc.get("tags", []))
    except (OSError, json.JSONDecodeError, StopIteration):
        pass
    ok, reasons = scan_upload(out, title, desc, tags)
    print(f"[security] {a.slug}: " + ("CLEAN" if ok else "; ".join(reasons)))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
