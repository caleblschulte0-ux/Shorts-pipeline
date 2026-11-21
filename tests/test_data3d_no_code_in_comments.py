"""A keyframe call written at the end of a COMMENT never runs.

2026-11-19: the card rewards heap "stays the same size in all three frames" (judge, several rounds) because
`heap.keyframe_insert(...)` had been typed after `; ` on a line that already ended in a comment. The same slip had
silently switched off the self-checkout machines' flashing lights twice in store/shots.py. Every data3d source is
scanned: no comment may carry a call that was meant to run.
"""
import pathlib
import re
import tokenize

ROOT = pathlib.Path(__file__).resolve().parents[1] / "tools" / "data3d"
CALL = re.compile(r";\s*[A-Za-z_][\w\.\[\]'\"]*\.(keyframe_insert|keyframe_delete)\(")


def test_no_keyframe_call_hides_in_a_comment():
    bad = []
    for p in ROOT.rglob("*.py"):
        with tokenize.open(p) as fh:
            for tok in tokenize.generate_tokens(fh.readline):
                if tok.type == tokenize.COMMENT and CALL.search(tok.string):
                    bad.append(f"{p.relative_to(ROOT)}:{tok.start[0]}")
    assert not bad, "a keyframe call sits inside a comment and never runs: " + ", ".join(bad)
