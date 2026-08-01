#!/usr/bin/env python3
"""The hook gate must grade the opening a VIEWER HEARS, not a fragment.

Four consecutive ~2-hour renders reported the same HOOK WEAK
['NO_GAP_NO_STAKES'] with an identical score, including one where the opening
line had been deliberately re-authored to clear the gate. The gate was grading
`narration.split(".")[0]` — the text before the first period — so a film opening
"Breathe in. Hold it. You are holding 10 sextillion molecules..." was judged on
the two words "Breathe in" and could never pass, whatever followed.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from hook_director import grade_line, opening_line  # noqa: E402

SHARED_AIR = ("Breathe in. Hold it. You are holding 10 sextillion molecules of "
              "air, and there is nothing on earth you can do to keep them — "
              "almost every one has already been inside someone else's lungs. "
              "Whose?")


def main():
    # 1. THE BUG: a hook opening on a short imperative was graded on it alone
    assert SHARED_AIR.split(".")[0] == "Breathe in"
    assert grade_line("Breathe in")["gates"] == ["NO_GAP_NO_STAKES"]
    got = opening_line(SHARED_AIR)
    assert not grade_line(got)["gates"], got
    print("ok  1. an opening that starts on a short imperative is no longer "
          "judged on those two words alone")

    # 2. a decimal is a number, not a sentence boundary
    d = "The average person loses 10.5 million cells a second. You never notice."
    assert d.split(".")[0] == "The average person loses 10"      # the old bug
    assert "10.5 million" in opening_line(d), opening_line(d)
    print("ok  2. a decimal no longer splits the number in half")

    # 3. the budget is respected — a hook is the first seconds, not the film
    long = " ".join(f"Sentence number {i} here." for i in range(40))
    assert len(opening_line(long).split()) <= 44, opening_line(long)
    print("ok  3. the opening is capped to roughly what is heard up front")

    # 4. a single-sentence hook still works, and empty stays empty
    one = "You will spend 26 years of your life asleep."
    assert opening_line(one) == one
    assert opening_line("") == "" and opening_line(None) == ""
    print("ok  4. single-sentence and empty narrations are handled")

    # 5. THE DIVERGENCE THAT CAUSED THE WASTED RENDER: the offline check and the
    #    production gate must extract the SAME text, or a story passes the cheap
    #    check and fails after two hours of rendering
    import check_hooks
    assert check_hooks.opening_line is opening_line
    print("ok  5. check_hooks and the production gate share one extractor")

    print("hook opening: 5/5 checks pass")


if __name__ == "__main__":
    main()
