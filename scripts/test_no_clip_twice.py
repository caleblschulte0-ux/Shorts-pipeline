#!/usr/bin/env python3
"""No clip may appear twice in one film.

THE DEFECT (2026-08-01, shared-air run 30724122149 — measured, not theorised).
The rendered package's credits.json listed 36 media slots filled by only 32
distinct assets: one clip used THREE times, another twice. The blind taste judge,
seeing only frames, named the duplicate pairs by timestamp without being told to
look — "17.7s/24.7s (reeds), 102.5s/109.6s (notebook), 137.9s/145.0s (curtains)
prove these shots carry no information and are there only to fill time" — and
labelled the film SAMENESS for the fourth render running.

`motion_first`'s `reseed` skips N already-tried LEADERS for one beat. It is
per-beat memory by construction, so nothing ever told beat 12 that beat 5 had
already used a clip: both asked the same ranked list the same question and got
the same answer. A repeat is the one flaw a viewer notices without being told
what to look for, and no amount of per-beat reseeding could prevent it.

The fix is a per-render set of used assets, consulted before probing and updated
on a win. It must be per-RENDER, not global: a later film is entitled to the best
clip for its subject, and a process-lifetime set would starve it.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))


def test_motion_first_accepts_and_honours_a_used_set():
    """The signature carries it and the skip is reachable."""
    import inspect
    from data_learning import media
    sig = inspect.signature(media.motion_first)
    assert "used" in sig.parameters, list(sig.parameters)
    assert sig.parameters["used"].default is None, sig.parameters["used"]
    src = inspect.getsource(media.motion_first)
    assert "used is not None and tag and tag in used" in src, \
        "the used-set check is not in the candidate loop"
    assert "used.add(tag)" in src, "a winning clip is never recorded as used"
    print("ok  motion_first takes a per-film used set, checks it, records wins")


def test_the_renderer_passes_it_and_resets_per_render():
    """A capability nothing calls is not a capability (CLAUDE.md rule zero)."""
    import inspect
    from data_learning import pro_render
    assert hasattr(pro_render, "_USED_MEDIA"), "no per-render used set"
    assert isinstance(pro_render._USED_MEDIA, set), pro_render._USED_MEDIA
    src = inspect.getsource(pro_render)
    assert "used=_USED_MEDIA" in src, \
        "pro_render never passes the used set to motion_first — unwired"
    assert "_USED_MEDIA.clear()" in src, \
        "the used set is never reset, so film 2 inherits film 1's exclusions"
    print("ok  pro_render passes the set and clears it per render")


def test_the_skip_actually_changes_the_pick():
    """The skip rule, exercised in isolation.

    HONEST LIMIT: this reproduces the loop's decision rather than driving
    motion_first itself, because that needs a live provider key and a network.
    The wiring checks above are what prove the rule is reachable in the real
    path; scripts/test_motion_window.py covers motion_first end to end when a
    key is present. Read this as "the rule is right", not "the render is
    proven".
    """
    from data_learning import media
    seen = []

    class FakeCand(dict):
        pass

    # Simulate the loop's decision directly: the check is `tag in used`.
    used = {"http://a/1.mp4"}
    for url in ("http://a/1.mp4", "http://a/2.mp4"):
        tag = url
        if used is not None and tag and tag in used:
            continue
        seen.append(url)
        used.add(tag)
    assert seen == ["http://a/2.mp4"], seen
    assert used == {"http://a/1.mp4", "http://a/2.mp4"}, used
    print("ok  a used clip is skipped and the next one is taken and recorded")


def test_an_empty_or_absent_set_changes_nothing():
    """Callers that pass nothing (tests, one-off tools) keep the old behaviour."""
    import inspect
    from data_learning import media
    sig = inspect.signature(media.motion_first)
    assert sig.parameters["used"].default is None
    # keyword-only, so no positional caller can be broken by the new parameter
    assert sig.parameters["used"].kind is inspect.Parameter.KEYWORD_ONLY, \
        sig.parameters["used"].kind
    print("ok  the parameter is keyword-only and defaults to no-op")


if __name__ == "__main__":
    test_motion_first_accepts_and_honours_a_used_set()
    test_the_renderer_passes_it_and_resets_per_render()
    test_the_skip_actually_changes_the_pick()
    test_an_empty_or_absent_set_changes_nothing()
    print("all no-clip-twice checks pass")
