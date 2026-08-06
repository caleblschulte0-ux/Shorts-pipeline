"""The showrunner gate, in ONE place, for every channel that publishes.

Why this module exists
----------------------
The headless-Claude SHOWRUNNER (`scripts/showrunner_review.py`) is the
channel's editor with a veto: it WATCHES the rendered video and grades it
against `docs/DIRECTOR.md`. Until now the *decision logic* around it — when a
missing verdict means hold, when an infra error means hold, what
`SHOWRUNNER=off` means on a publish run — lived inline in
`scripts/post_stories.py`, and so it protected exactly one channel.

The numbers in `docs/SYSTEM_AUDIT.md` §B are the argument:

    explainer   1 video/day, showrunner-gated,  best video 1,063 views
    trending    6 videos/day, ungated,          best video    45 views

Six times the volume, one twenty-third the ceiling. Six unwatched videos a
day is six chances to publish something nobody would have approved. So the
gate becomes shared infrastructure and trending gets it too — copying the
block into a second channel would have been the wrong fix (and is forbidden:
"never copy shared logic into a channel").

The rules this module encodes — none of them negotiable
-------------------------------------------------------
1. **A BLOCK is sovereign.** Code may only ever ADD blocks. There is no path
   through this function that turns a brain BLOCK into a ship, and
   `decide()` composes with `or` for exactly that reason.
2. **A publish run fails CLOSED.** No verdict, an infra error, a timeout, a
   missing API key — none of those are evidence the video is good, so the
   video is held. Only a preview/dry run fails open, so that iteration is not
   blocked by infrastructure.
3. **`SHOWRUNNER=off` is refused on a publish run.** The taste gate is the
   price of publishing. It can be switched off for previews and nothing else.
4. **Every verdict is appended to the ledger** (`state/showrunner_verdicts.jsonl`),
   which is the showrunner's durable memory.

`decide()` is pure — no ffmpeg, no network, no clock — so the fail-closed
semantics are testable without rendering anything. `run()` is the thin I/O
wrapper channels actually call.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

#: Env var a preview run can set to skip the gate. Refused on a publish run.
ENV_FLAG = "SHOWRUNNER"
_OFF = ("off", "0", "false", "no")


def enabled(env: dict | None = None) -> bool:
    """Is the gate switched on? (Only meaningful for non-publish runs — a
    publish run refuses to honour 'off' at all; see `decide`.)"""
    env = os.environ if env is None else env
    return str(env.get(ENV_FLAG, "on")).lower() not in _OFF


def decide(*, will_upload: bool, gate_on: bool, verdict: dict | None,
           error: BaseException | str | None = None) -> dict:
    """Block-or-ship, as a pure function. The whole fail-closed policy.

    Args:
        will_upload: True on a real publish run; False for preview/dry-run.
        gate_on:     the resolved `SHOWRUNNER` switch.
        verdict:     what `showrunner_review.review_video` returned, or None
                     if it never produced one.
        error:       the exception (or message) if the review blew up.

    Returns a dict with `blocked`, `reason`, and `ran`.

    Every branch that can block is an `or` of independent conditions. Adding
    a new reason to hold is safe; there is deliberately no branch that clears
    a hold set by an earlier one.
    """
    reasons: list[str] = []

    if not gate_on:
        if will_upload:
            # Rule 3. The one thing you may never do to fix a red gate.
            return {"blocked": True, "ran": False,
                    "reason": "SHOWRUNNER=off is not allowed on a publish run",
                    "verdict": {}}
        return {"blocked": False, "ran": False,
                "reason": "showrunner skipped (preview run)", "verdict": {}}

    if error is not None:
        # Rule 2. An infra failure is not evidence of quality.
        if will_upload:
            return {"blocked": True, "ran": False,
                    "reason": f"showrunner failed on a publish run "
                              f"(fail-closed): {str(error)[:160]}",
                    "verdict": verdict or {}}
        return {"blocked": False, "ran": False,
                "reason": f"showrunner skipped (preview, not blocking): "
                          f"{str(error)[:160]}",
                "verdict": verdict or {}}

    verdict = verdict or {}
    # Rule 1 — the brain's own call, first and unconditional.
    if str(verdict.get("verdict")) == "block":
        reasons.append(f"showrunner BLOCK: {verdict.get('one_line') or ''}"
                       .strip())
    # Rule 2 — on a publish run, only an EXPLICIT AFFIRMATIVE ships.
    #
    # This used to be two negative checks: token == "block" blocks, score
    # None blocks. The doctor's 2026-08-05 report (finding 3aae…, HIGH)
    # caught what that leaves open: a malformed verdict — an unknown token
    # like "error" carrying a numeric score — matched neither check and
    # SHIPPED. "Not refused" is not the same thing as "approved", and in a
    # fail-closed gate the difference is the whole design. The reviewer's
    # token domain is exactly {"ship", "block"} (`decide_verdict`), so on a
    # publish run anything that is not literally "ship" with a bounded
    # numeric score is treated as no verdict at all.
    if will_upload:
        tok = str(verdict.get("verdict") or "").lower()
        score = verdict.get("score")
        # The reviewer scores 0-100 (compute_score; MIN_SCORE defaults 70).
        score_ok = (isinstance(score, (int, float))
                    and not isinstance(score, bool) and 0 <= score <= 100)
        if tok != "block" and (tok != "ship" or not score_ok):
            reasons.append(
                f"showrunner verdict is not an explicit ship "
                f"(verdict={tok or 'missing'!r}, score={score!r}) — "
                f"fail-closed on a publish run")

    return {"blocked": bool(reasons), "ran": True,
            "reason": "; ".join(r for r in reasons if r),
            "verdict": verdict}


def run(mp4, *, slug: str, context: dict | None = None,
        will_upload: bool, env: dict | None = None,
        sidecar: bool = True) -> dict:
    """Render-side wrapper: review the video, record it, decide.

    Never raises — a gate that crashes the run is a gate that caused the
    outage it exists to prevent. Any failure is routed through `decide`,
    which holds the video on a publish run and lets it through on a preview.
    """
    mp4 = Path(mp4)
    gate_on = enabled(env)
    if not gate_on:
        return decide(will_upload=will_upload, gate_on=False, verdict=None)

    verdict: dict | None = None
    error: BaseException | None = None
    try:
        from scripts import showrunner_review as _sr
        verdict = _sr.review_video(mp4, context=dict(context or {}))
        if sidecar:
            try:
                mp4.with_suffix(".showrunner.json").write_text(
                    json.dumps(verdict, indent=2))
            except Exception:                            # noqa: BLE001
                pass                     # a sidecar is a convenience, not state
        try:
            _sr.append_ledger(slug, verdict)   # rule 4: durable memory
        except Exception:                                # noqa: BLE001
            pass
    except KeyboardInterrupt:
        raise                                  # Ctrl-C is not a gate failure
    except BaseException as exc:               # noqa: BLE001 — SystemExit too:
        error = exc                            # a rogue sys.exit() downstream
                                               # must not read as "approved".

    out = decide(will_upload=will_upload, gate_on=True, verdict=verdict,
                 error=error)
    out["slug"] = slug
    return out


def log(result: dict, slug: str | None = None) -> str:
    """One human line for a run log. Returns it as well as printing, so
    callers can fold it into their own report."""
    tag = "BLOCK" if result.get("blocked") else "SHIP"
    v = result.get("verdict") or {}
    line = (f"[{slug or result.get('slug') or '?'}] showrunner {tag} "
            f"score={v.get('score')}"
            + (f" — {result['reason']}" if result.get("reason")
               else (f" — {v.get('one_line')}" if v.get("one_line") else "")))
    print(line, flush=True)
    for fx in (v.get("fixes") or [])[:5]:
        print(f"   fix: {fx}", flush=True)
    return line
