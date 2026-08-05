#!/usr/bin/env python3
"""Phase A (4:30) — find media, judge it, write the day's ask. NO RENDER.

Reads the day's authored packages, records what media each shot actually has,
runs the script-aware judge over every shot, and writes ONE bundle describing
the gaps plus the scripts for punch-up. Then stops: rendering waits until
ChatGPT has answered, because both the script and the visuals are still going
to change.

    python scripts/exchange_phase_a.py --date 20260730 --channel trending
    python scripts/exchange_phase_a.py --date 20260730 --dry-run

Writes:
    exchange/bundles/<date>/bundle.json
    exchange/bundles/<date>/READY

Exit 0 always unless the packages directory is unreadable — a day with no
gaps is a valid, successful Phase A (it just asks for nothing).
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from funnel import media_judge                     # noqa: E402
from shared import authoring_brief as brief         # noqa: E402
from shared import channel_registry as reg          # noqa: E402
from shared import exchange_bundle as xb           # noqa: E402
from shared import media_checkpoint as mc          # noqa: E402
from shared.fsutil import atomic_write_json        # noqa: E402

PACKAGE_DIRS = {
    "trending": "state/trending_packages",
    "third": "state/third_packages",
}


# A package directory also accumulates config and reports. Counting those as
# packages is not cosmetic: the slate count is what decides whether ChatGPT is
# asked to take over, so one stray `_schedule.json` next to five real packages
# reads as a full six and the takeover never fires.
NON_PACKAGE_NAMES = frozenset({
    "report.json", "manifest.json", "index.json", "meta.json",
    "authored_report.json", "phase_b_report.json",
})
# Fields that only a real package carries. A report or a config has none.
_PACKAGE_MARKERS = ("script", "text", "series", "shots", "subreddit",
                    "broll_query", "segments")


def is_package(obj) -> bool:
    """True for a renderable package, False for config/report/metadata."""
    if not isinstance(obj, dict):
        return False
    return any(obj.get(k) for k in _PACKAGE_MARKERS)


def load_packages(channel: str, date: str) -> list[dict]:
    base = ROOT / PACKAGE_DIRS.get(channel, PACKAGE_DIRS["trending"])
    # Packages live either in a per-date folder or flat with a date prefix.
    candidates = sorted(glob.glob(str(base / str(date) / "*.json")))
    if not candidates:
        candidates = sorted(glob.glob(str(base / f"*{date}*.json")))
    out = []
    for p in candidates:
        name = Path(p).name
        if name.startswith("_") or name in NON_PACKAGE_NAMES:
            continue                                 # config, not content
        try:
            pkg = json.loads(Path(p).read_text())
        except Exception:                            # noqa: BLE001
            print(f"[phase-a] skipping unreadable package {p}")
            continue
        if not is_package(pkg):
            print(f"[phase-a] skipping non-package file {name} "
                  f"(no script/text/series/shots)")
            continue
        pkg.setdefault("slug", Path(p).stem)
        pkg["_path"] = p
        out.append(pkg)
    return out


def resolve_media(pkg: dict, *, verbose: bool = True) -> dict:
    """Do the media FINDING that normally happens at render time, now — so the
    judge scores what we would actually put on screen rather than an empty
    package. `enrich_package` pins `image_url` onto every shot it can cover
    (make_explainer_stacked.py:2556 does the same call at render time).

    Best-effort: without a network or an LLM key this simply attaches less,
    and those shots judge as `missing`, which is the correct answer."""
    try:
        from funnel import entity_media
        return entity_media.enrich_package(pkg, verbose=verbose)
    except Exception as exc:                         # noqa: BLE001
        print(f"[phase-a] media resolution unavailable ({exc}) — "
              f"judging whatever the package already carries")
        return pkg


def usage_penalties(pkg: dict) -> dict:
    """Repetition penalty per shot from the cross-video ledger, if available."""
    try:
        from funnel import media_usage
    except Exception:                                # noqa: BLE001
        return {}
    pen = {}
    for i, shot in enumerate(pkg.get("shots") or []):
        url = shot.get("image_url")
        if not url:
            continue
        try:
            score = media_usage.penalty(url)         # type: ignore[attr-defined]
            if score:
                pen[i] = float(score)
        except Exception:                            # noqa: BLE001
            continue
    return pen


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", required=True, help="YYYYMMDD or YYYY-MM-DD")
    ap.add_argument("--channel", default="trending",
                    choices=sorted(PACKAGE_DIRS))
    ap.add_argument("--dry-run", action="store_true",
                    help="print the bundle, write nothing")
    ap.add_argument("--no-resolve", action="store_true",
                    help="skip media finding; judge only what is pinned "
                         "(offline testing)")
    ap.add_argument("--target", type=int, default=None,
                    help="override the registry's package count for this run "
                         "(normally omitted — config/channel_registry.json "
                         "decides)")
    ap.add_argument("--rebuild-contract", action="store_true",
                    help="MIGRATION: re-resolve the registry for a date whose "
                         "bundle already froze one. Moves the goalposts under "
                         "a worker that may already be running.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    packages = load_packages(args.channel, args.date)

    # ---- THE CONTRACT --------------------------------------------------
    # Resolved from config/channel_registry.json ONCE per production date and
    # frozen into the bundle. A re-run (backstop cron, manual dispatch) reuses
    # the frozen copy: the 06:00 media worker may already be generating
    # against those numbers, and re-resolving would leave half a slate built
    # to one plan and half to another.
    try:
        frozen = xb.existing_contract(args.date)
        if frozen and not args.rebuild_contract:
            contract = frozen
            print(f"[phase-a] reusing the FROZEN contract for {args.date} "
                  f"(registry rev {contract.get('registry_revision')}, "
                  f"sha {str(contract.get('registry_sha256'))[:12]}…) — a "
                  f"registry change since then starts with the next date")
            live = reg.sha256()
            if live != contract.get("registry_sha256"):
                print(f"::notice::the registry has changed since {args.date}'s "
                      f"bundle was created (live sha {live[:12]}…). That is "
                      f"fine and expected — the new rules apply from the next "
                      f"bundle. Use --rebuild-contract only to deliberately "
                      f"migrate this open day.")
        else:
            contract = reg.plan(args.date,
                                {args.channel: packages})
            if frozen:
                print(f"::warning::--rebuild-contract: re-resolving {args.date} "
                      f"from registry rev {contract['registry_revision']}. Any "
                      f"worker already running is now on stale numbers.")
    except reg.RegistryError as exc:
        # FAIL HONESTLY. Falling back to a historical mix is how a retired
        # format gets authored on a day nobody is watching.
        print(f"::error::channel registry unusable — {exc}")
        return 1

    target = (args.target if args.target is not None
              else (contract["channels"].get(args.channel) or {})
              .get("target_count", 0))
    print(f"[phase-a] contract: {args.channel} wants {target} — "
          f"{reg.mix_sentence(args.channel)}")

    # AUTHORING TAKEOVER. A short day means the Claude Routine did not run.
    # Rather than exit 0 with nothing to ask for — which is exactly how a
    # dead authoring night stayed invisible — put an authoring brief in the
    # bundle and let ChatGPT be the brain.
    authoring_request = None
    if len(packages) < target:
        authoring_request = brief.build_request(
            args.date, args.channel, have_packages=packages,
            target=args.target,
            reason=(f"only {len(packages)} of {target} packages exist "
                    f"for {args.date}: the Claude authoring Routine did "
                    f"not run"))
        print(f"[phase-a] TAKEOVER: {len(packages)}/{target} packages — "
              f"asking ChatGPT to author {authoring_request['write']} "
              f"({', '.join(f'{n}x{f}' for f, n in authoring_request['mix'].items() if n)})")

    # EVERY channel's ask, not just trending's. The operator's rule: if a
    # channel appears here, Claude left it nothing today and ChatGPT is its
    # brain. Explainer asks for WORDS (its numbers are already real);
    # curiosity asks for queue stock. Third is absent by nature — its package
    # is a capture recipe for a clip that does not exist yet.
    channel_requests = brief.all_requests(args.date, authoring_request)
    for ch, req in channel_requests.items():
        if ch == "trending":
            continue
        print(f"[phase-a] TAKEOVER {ch}: {req.get('job', 'author')} "
              f"x{req.get('write', 0)} — {req.get('reason', '')[:70]}")

    if not packages and not channel_requests:
        print(f"[phase-a] no packages for {args.channel} {args.date} — "
              f"nothing to ask for")
        return 0

    reports = []
    for pkg in packages:
        if not args.no_resolve:
            resolve_media(pkg, verbose=not args.json)
        report = media_judge.judge_package(
            pkg, None, usage_penalties=usage_penalties(pkg))
        reports.append(report)

    bundle = xb.build_bundle(args.date, packages, reports,
                             authoring_request, channel_requests, contract)

    if args.json:
        print(json.dumps(bundle, indent=2)[:4000])
    else:
        print(f"[phase-a] {args.channel} {args.date}: "
              f"{len(packages)} package(s)")
        for r in reports:
            c = r.get("counts") or {}
            print(f"  {r.get('slug')}: {r.get('shot_count')} shots  "
                  f"strong={c.get('strong', 0)} weak={c.get('weak', 0)} "
                  f"missing={c.get('missing', 0)}")
            for g in (r.get("gaps") or [])[:4]:
                why = "; ".join(g.get("reasons") or [])[:90]
                print(f"     gap shot {g.get('shot_index')}: "
                      f"{g.get('verdict')} — {why}")
        cnt = bundle["counts"]
        print(f"[phase-a] asking ChatGPT for {cnt['requests']} asset(s) "
              f"({cnt['animations']} animation) + punch-up on "
              f"{cnt['packages']} script(s)")

    if args.dry_run:
        print("[phase-a] dry run — nothing written")
        return 0

    # DO NOT MOVE THE GOALPOSTS UNDER A WORKER THAT IS ALREADY RUNNING.
    # If checkpoints exist, the 06:00 media worker has started (or finished).
    # Rewriting the ask now orphans its work. A re-judge that changes nothing
    # is harmless and allowed through; a changed ask is refused unless the
    # operator explicitly migrates the day.
    existing_cps = mc.all_checkpoints(args.date)
    if existing_cps and not args.rebuild_contract:
        live = mc.ask_fingerprint(bundle)
        frozen_id = mc.bundle_identity(args.date)
        if frozen_id and live != frozen_id:
            print(f"::warning::{len(existing_cps)} checkpoint(s) already "
                  f"exist for {args.date} and the ASK has changed "
                  f"({str(frozen_id)[:12]}… -> {live[:12]}…). Refusing to "
                  f"rewrite the bundle — that would orphan every image the "
                  f"media worker has already verified. Re-run with "
                  f"--rebuild-contract to migrate the day deliberately.")
            print(f"[phase-a] leaving {args.date}'s bundle as it stands")
            return 0
        print(f"[phase-a] {len(existing_cps)} checkpoint(s) exist and the ask "
              f"is unchanged — safe to refresh the bundle")

    for pkg in packages:
        pkg_path = pkg.get("_path")
        if not pkg_path:
            continue
        try:
            saved = {k: v for k, v in pkg.items() if k != "_path"}
            atomic_write_json(Path(pkg_path), saved)
        except Exception as exc:                         # noqa: BLE001
            print(f"[phase-a] WARN could not save resolved media for "
                  f"{pkg.get('slug')}: {exc}")

    path = xb.write_bundle(args.date, packages, reports,
                           authoring_request, channel_requests, contract)
    if path is None:
        print("[phase-a] ERROR: could not write bundle")
        return 1
    ready = xb.mark_ready(args.date)
    print(f"[phase-a] wrote {path.relative_to(ROOT)}")
    # The identity both workers must record in every checkpoint. Printed so a
    # run log shows exactly which ask the day's checkpoints belong to — if
    # Phase A is re-run with different prompts this string changes and every
    # earlier checkpoint stops matching, which is the intended behaviour.
    # PUBLISH THE IDENTITY, and keep it stable while the ask is.
    #
    # Phase A runs on every auto-merge — six times on 2026-08-01, the last
    # five hours AFTER the 06:00 media worker finished. When identity was the
    # sha256 of bundle.json's bytes, each of those rewrites silently killed
    # every checkpoint written before it, and a DONE run (which now requires
    # checkpoints) would have refused all 17 verified images. The sidecar
    # moves only when `ask_fingerprint` moves.
    ident = mc.write_bundle_identity(args.date, xb.read_bundle(args.date))
    if ident:
        print(f"[phase-a] bundle identity {ident[:16]}… "
              f"-> exchange/bundles/{args.date}/{mc.IDENTITY_FILE}")
        print(f"[phase-a] checkpoints go in "
              f"exchange/bundles/{args.date}/"
              f"{mc.PROGRESS_DIRNAME}/<safe_request_id>.json")
    if ready:
        print(f"[phase-a] wrote {ready.relative_to(ROOT)} — "
              f"commit these; ChatGPT answers next")
    return 0


if __name__ == "__main__":
    sys.exit(main())
