#!/usr/bin/env python3
"""Acceptance run for the dynamic channel contract, offline, in seven steps.

The claim being tested is not "the code works" but "operational policy has
exactly one home". So this changes NOTHING except `config/channel_registry.json`
(via a fixture copy) and watches the whole pipeline move:

    1. Build a bundle from the CURRENT registry.
    2. Confirm the resolved slate is the live production ruling.
    3. Swap in a materially different plan — different counts, a retired
       format brought back, a brand-new format, a disabled channel.
    4. Build the NEXT date's bundle.
    5. Show ChatGPT's requests, the authoring shortfall, media requirements,
       validation and promotion all changed — with no code edited.
    6. Show date one's bundle is still byte-identical and reproducible.
    7. Report.

    python scripts/registry_acceptance.py          # human-readable
    python scripts/registry_acceptance.py --json   # machine-readable

Exit 0 = policy propagates from the registry alone. Exit 1 = something is
still carrying its own copy of the rules; the failing step names it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from funnel import media_judge                       # noqa: E402
from shared import authoring_brief as brief          # noqa: E402
from shared import channel_registry as reg           # noqa: E402
from shared import exchange_bundle as xb             # noqa: E402
from shared import package_buffer as buf             # noqa: E402
from tests.registry_fixture import build, registry   # noqa: E402

DAY_ONE = "29991201"
DAY_TWO = "29991202"

#: Deliberately unlike anything this channel has ever shipped: a different
#: total, a different lead format, a format with no code written for it, and
#: a channel switched off.
NEW_PLAN = {"reddit_story": 5, "quiz_card": 3}
QUIZ = {"state": "active", "target": 3, "renderer": "make_quiz.py",
        "detect": {"field": "format", "equals": "quiz_card"},
        "required_fields": ["format", "slug", "title", "questions"],
        "media": {"shots": True, "chatgpt_supplies_images": True,
                  "shots_min": 4},
        "chatgpt_roles": ["media_worker", "takeover_authoring"]}


def _reddit(slug):
    script = ("My neighbour kept parking in my spot. So I called the city. "
              "They towed him twice in one week and then he moved away.")
    return {"slug": slug, "subreddit": "pettyrevenge", "title": f"T {slug}",
            "script": script, "hashtags": ["#a"] * 6, "music_vibe": "calm",
            "shots": [{"phrase": "So I called the city", "query": "city"}],
            "punches": [{"phrase": "They towed him twice in one week",
                         "text": "TWICE", "color": "#ff3030"}]}


class Run:
    def __init__(self):
        self.steps: list[dict] = []
        self.tmp = Path(tempfile.mkdtemp(prefix="registry-acceptance-"))
        self.saved = xb.BUNDLE_ROOT
        xb.BUNDLE_ROOT = self.tmp / "bundles"

    def close(self):
        xb.BUNDLE_ROOT = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def step(self, n, name):
        self.steps.append({"step": n, "name": name, "checks": [], "ok": True})
        return self.steps[-1]

    def check(self, step, ok, detail):
        step["checks"].append({"ok": bool(ok), "detail": detail})
        if not ok:
            step["ok"] = False
        return bool(ok)

    def bundle_for(self, date, packages, contract):
        reports = [media_judge.judge_package(p, None) for p in packages]
        request = None
        if sum(reg.shortfall("trending", packages).values()):
            request = brief.build_request(date, "trending",
                                          have_packages=packages)
        xb.write_bundle(date, packages, reports, request,
                        {"trending": request} if request else None, contract)
        return xb.read_bundle(date)


def run(verbose=True) -> dict:                        # noqa: C901
    r = Run()
    try:
        # -- 1. a bundle from the CURRENT registry --------------------------
        s = r.step(1, "Build a bundle from the live registry")
        live_plan = reg.plan(DAY_ONE, {"trending": []})
        b1 = r.bundle_for(DAY_ONE, [], live_plan)
        day_one_bytes = (xb.bundle_dir(DAY_ONE) / "bundle.json").read_bytes()
        day_one_sha = hashlib.sha256(day_one_bytes).hexdigest()
        r.check(s, isinstance(b1.get("contract"), dict),
                "bundle.json carries a frozen contract")
        for field in ("source_commit", "registry_revision", "registry_sha256",
                      "production_date", "channels", "totals"):
            r.check(s, field in b1["contract"], f"contract.{field} present")
        t1 = b1["contract"]["channels"]["trending"]
        for field in ("target_count", "target_mix", "shortfall",
                      "active_formats", "retired_formats", "chatgpt_roles",
                      "media_requirements", "protected_fields",
                      "allowed_editorial_mutations", "doctrine",
                      "package_schema", "response_schema", "paths",
                      "failure_policy"):
            r.check(s, field in t1, f"contract.channels.trending.{field}")
        r.check(s, all(d.get("sha256") for d in t1["doctrine"]),
                f"{len(t1['doctrine'])} doctrine file(s) hashed into the "
                f"snapshot")

        # -- 2. it is the live production ruling ----------------------------
        s = r.step(2, "The resolved slate is today's real ruling")
        r.check(s, t1["target_mix"] == reg.target_mix("trending"),
                f"trending target_mix = {t1['target_mix']}")
        r.check(s, t1["retired_formats"] == reg.retired_formats("trending"),
                f"retired = {t1['retired_formats']}")
        r.check(s, "text_card" not in b1["authoring_request"]["formats"],
                "the retired format is absent from the authoring brief")
        r.check(s, b1["authoring_request"]["write"]
                == reg.target_count("trending"),
                f"ChatGPT is asked for {b1['authoring_request']['write']}")
        before = {
            "mix": dict(reg.target_mix("trending")),
            # The LIVE revision at freeze time — never a hardcoded number.
            # This said `== 1` until 2026-08-05, which was true on the day it
            # was written and false the moment the registry revision moved
            # (rev 3 by then). It went unnoticed because those revision bumps
            # were pushed straight to main, skipping the auto-merge gate that
            # runs this script — the gate can only guard what goes through it.
            "revision": reg.revision(),
            "bank_formats": list(buf.formats()),
            "brief_formats": sorted(b1["authoring_request"]["formats"]),
            "channels": list(reg.channel_ids()),
        }

        # -- 3+4. swap the registry, build the NEXT date --------------------
        s = r.step(3, "Change ONLY the registry to a different plan")
        obj = build(NEW_PLAN, retired=["graph_race"],
                    extra_formats={"quiz_card": dict(QUIZ)},
                    revision=before["revision"] + 1)
        obj["channels"]["curiosity"]["enabled"] = False
        with registry(registry_object=obj):
            r.check(s, reg.revision() == before["revision"] + 1,
                    f"registry revision bumped to {reg.revision()}")
            r.check(s, reg.target_mix("trending") == NEW_PLAN,
                    f"new mix {reg.target_mix('trending')}")

            s = r.step(4, "Build the next date's bundle")
            plan2 = reg.plan(DAY_TWO, {"trending": [_reddit("carry-over")]})
            b2 = r.bundle_for(DAY_TWO, [_reddit("carry-over")], plan2)
            t2 = b2["contract"]["channels"]["trending"]

            # -- 5. everything moved, with no code edited -------------------
            s = r.step(5, "Every consumer followed, with no code edited")
            r.check(s, t2["target_mix"] == NEW_PLAN,
                    f"Phase A plan  -> {t2['target_mix']}")
            r.check(s, t2["shortfall"] == {"reddit_story": 4, "quiz_card": 3},
                    f"shortfall     -> {t2['shortfall']} "
                    f"(one reddit_story already existed)")
            req2 = b2["authoring_request"]
            r.check(s, sorted(req2["formats"]) == ["quiz_card",
                                                   "reddit_story"],
                    f"ChatGPT asked  -> {sorted(req2['formats'])}")
            r.check(s, req2["write"] == 7, f"authoring write -> {req2['write']}")
            r.check(s, "graph_race" in req2["retired_formats"],
                    "graph_race now reads as RETIRED in the brief")
            r.check(s, req2["formats"]["quiz_card"]["media"]
                    ["chatgpt_supplies_images"],
                    "media requirements follow the new format registry")
            r.check(s, list(buf.formats()) == sorted(NEW_PLAN),
                    f"reserve bank  -> {list(buf.formats())}")
            r.check(s, buf.low_water()["reddit_story"] == 5 * buf.LOW_WATER_DAYS,
                    "bank low-water scaled with the new target")

            # validation + promotion
            zombie = {"format": "graph_race", "slug": "zombie-graph",
                      "title": "Z", "y_label": "y", "duration": 13,
                      "source": "s", "years": [1, 2], "hashtags": ["#a"] * 6,
                      "series": [{"name": "n", "color": "#fff", "icon": "US",
                                  "values": [1, 2]}], "music_vibe": "dark"}
            problems = brief.validate_authored(zombie)
            r.check(s, any("retired" in p for p in problems),
                    "promotion refuses the newly-retired format")
            ok, why = buf.eligible(zombie)
            r.check(s, not ok and any("retired" in w for w in why),
                    "the reserve bank refuses it too")
            quiz = {"format": "quiz_card", "slug": "q1", "title": "Q",
                    "questions": ["a"]}
            r.check(s, reg.classify(quiz, "trending") == "quiz_card",
                    "the brand-new format classifies without a code change")
            r.check(s, "curiosity" not in reg.channel_ids()
                    and "curiosity" not in b2["contract"]["channels"],
                    "the disabled channel is gone from the plan")
            r.check(s, sorted(b2["contract"]["channels"])
                    != sorted(b1["contract"]["channels"]),
                    "the channel set itself changed between the two days")
            r.check(s, before["mix"] != reg.target_mix("trending")
                    and before["bank_formats"] != list(buf.formats())
                    and before["brief_formats"] != sorted(req2["formats"]),
                    "plan, bank and brief all differ from step 1")

            # -- 6. day one is untouched ---------------------------------
            s = r.step(6, "Day one's bundle is unchanged and reproducible")
            now = (xb.bundle_dir(DAY_ONE) / "bundle.json").read_bytes()
            r.check(s, hashlib.sha256(now).hexdigest() == day_one_sha,
                    "byte-identical after the registry changed")
            frozen = xb.existing_contract(DAY_ONE)
            r.check(s, frozen["registry_revision"] == before["revision"],
                    f"still pinned to registry rev "
                    f"{frozen['registry_revision']} (frozen at "
                    f"{before['revision']}), not {reg.revision()}")
            r.check(s, frozen["channels"]["trending"]["target_mix"]
                    == before["mix"],
                    "day one still contracts the OLD mix")
            r.check(s, "curiosity" in frozen["channels"],
                    "day one still contracts the since-disabled channel")
            rebuilt = xb.existing_contract(DAY_ONE)
            r.check(s, rebuilt == frozen,
                    "re-reading the frozen contract is deterministic")
            r.check(s, frozen.get("source_commit") is not None,
                    f"doctrine is readable from source_commit "
                    f"{str(frozen.get('source_commit'))[:12]}")

        # -- 7. and the live registry is untouched by all of that -----------
        s = r.step(7, "The live registry was never modified")
        r.check(s, reg.target_mix("trending") == before["mix"],
                f"back to the real ruling {reg.target_mix('trending')}")
        r.check(s, reg.channel_ids() == before["channels"],
                "channel set restored")
        r.check(s, reg.validate(reg.load()) == [], "and it is still valid")

        steps = r.steps
    finally:
        r.close()

    ok = all(st["ok"] for st in steps)
    out = {"ok": ok, "steps": steps,
           "passed": sum(1 for st in steps if st["ok"]), "total": len(steps)}
    if verbose:
        for st in steps:
            print(f"[{'PASS' if st['ok'] else 'FAIL'}] step {st['step']}: "
                  f"{st['name']}")
            for c in st["checks"]:
                print(f"        {'ok ' if c['ok'] else 'NO '} {c['detail']}")
        verdict = ("policy lives in ONE place" if ok else
                   "SOMETHING STILL CARRIES ITS OWN COPY")
        print(f"\n{out['passed']}/{out['total']} steps passed — {verdict}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = run(verbose=not args.json)
    if args.json:
        print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
