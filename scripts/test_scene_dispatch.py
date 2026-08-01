#!/usr/bin/env python3
"""EVERY scene/card kind the renderer dispatches must accept the arguments the
renderer actually passes it.

This is the regression test for a class of bug that cost a full CI render: the
nine money-era scene builders accepted `extra` (the expression payload) while
the eight life-era ones did not, and pro_render's dispatch passes `extra=` to
all sixteen. money-goes only ever used money scenes, so the canonical producer
crashed on the FIRST time/life scene any story tried to use — fail-closed, no
video, 225 wasted seconds.

The test reads the dispatch table out of pro_render itself, so a newly
registered scene is covered automatically instead of being trusted.
"""
from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from data_learning import scenes  # noqa: E402


def dispatched_scene_kinds() -> dict[str, str]:
    """{'scene_sleep': 'sleep_scene', ...} parsed from pro_render's table."""
    src = (REPO / "data_learning" / "pro_render.py").read_text()
    return dict(re.findall(r'"(scene_[a-z_]+)":\s*scenes\.([a-z_]+)', src))


def dispatch_kwargs() -> set[str]:
    """The kwargs pro_render passes to a generic scene builder. The call spans
    several lines, so scan with balanced parens rather than splitting on the
    first ')' (which finds only the inner shot.get(...) call)."""
    src = (REPO / "data_learning" / "pro_render.py").read_text()
    i = src.index("return fn(") + len("return fn(")
    depth, out = 1, []
    while depth:
        ch = src[i]
        depth += (ch == "(") - (ch == ")")
        if depth:
            out.append(ch)
        i += 1
    call = "".join(out)
    # only TOP-level kw= names, i.e. not those inside nested calls
    flat, depth = [], 0
    for ch in call:
        depth += (ch == "(") - (ch == ")")
        flat.append(ch if depth == 0 else " ")
    return set(re.findall(r"(\w+)\s*=", "".join(flat)))


def main():
    table = dispatched_scene_kinds()
    assert len(table) >= 16, f"only found {len(table)} scene kinds — parse broke"
    kwargs = dispatch_kwargs()
    assert "extra" in kwargs and "number" in kwargs and "label" in kwargs, kwargs
    print(f"ok  1. dispatch table: {len(table)} scene kinds, passing {sorted(kwargs)}")

    # scene_money has its own dispatch branch with extra args (upto/final),
    # so the generic-table regex can mis-bind it; check it separately below.
    table.pop("scene_money", None)
    missing = []
    for kind, fname in sorted(table.items()):
        fn = getattr(scenes, fname, None)
        if fn is None:
            missing.append(f"{kind}: scenes.{fname} does not exist")
            continue
        params = inspect.signature(fn).parameters
        takes_var_kw = any(p.kind is inspect.Parameter.VAR_KEYWORD
                           for p in params.values())
        for kw in kwargs:
            if kw not in params and not takes_var_kw:
                missing.append(f"{kind} ({fname}) cannot accept {kw!r}")
    assert not missing, ("the renderer passes arguments these builders reject "
                         "— a render using them dies fail-closed:\n  "
                         + "\n  ".join(missing))
    print(f"ok  2. all {len(table)} builders accept every dispatched argument")

    # the expression payload must be genuinely OPTIONAL: a baseline call with
    # extra=None has to work for every scene (that is the default render path)
    for kind, fname in sorted(table.items()):
        sig = inspect.signature(getattr(scenes, fname))
        p = sig.parameters.get("extra")
        assert p is not None and p.default is None, \
            f"{fname}: `extra` must default to None (got {p})"
    print("ok  3. `extra` is optional everywhere — baseline path unchanged")

    # scene_money's own branch
    mp = inspect.signature(scenes.money_scene).parameters
    for kw in ("number", "label", "extra", "upto", "final"):
        assert kw in mp, f"money_scene cannot accept {kw!r}"
    assert mp["extra"].default is None
    print("ok  4. scene_money's dedicated dispatch matches money_scene")

    print(f"scene dispatch: 4/4 checks pass ({len(table)} kinds verified)")


if __name__ == "__main__":
    main()
