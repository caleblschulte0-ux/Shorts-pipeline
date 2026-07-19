#!/usr/bin/env python3
"""THE QUALITY GATE — judge a render AND remember it, in one command.

This is the turnkey step that makes "improve over time" automatic. Point it at a
finished render + its beatmap and it:

  1. runs the INTEREST judge (dead time, appeal, novelty),
  2. runs the COOL judge (LONG_HOLD / DULL / LOW_MOTION / STILL_WHEN_MOTION_EXISTS
     / FRAGMENT_OF_THE_SPECTACLE hands),
  3. feeds both verdicts + the render log into the SHOWRUNNER memory
     (data_learning/quality_memory), which re-learns the recurring failures, and
  4. prints the learned advice for the NEXT render.

Run it after every render. The lessons compound in the ledger instead of being
re-discovered each time.

    python scripts/quality_gate.py <render.mp4> --beatmap <beatmap.json> \
        --slug hurricane --label v10 [--log <render.log>] [--out <dir>]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def _run_judge(script: str, args: list[str]) -> bool:
    try:
        subprocess.run([sys.executable, str(REPO / "scripts" / script), *args],
                       check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[gate] {script} failed ({e}) — recording what we have")
        return False


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("render", type=Path)
    ap.add_argument("--beatmap", type=Path, required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--log", type=Path)
    ap.add_argument("--out", type=Path,
                    help="judge-output dir (default: alongside the render)")
    a = ap.parse_args(argv)

    out = a.out or a.render.parent / f"{a.render.stem}_gate"
    interest_dir = out / "interest"
    cool_dir = out / "cool"
    interest_dir.mkdir(parents=True, exist_ok=True)
    cool_dir.mkdir(parents=True, exist_ok=True)

    _run_judge("interest_judge.py", [str(a.render), "--out", str(interest_dir)])
    _run_judge("cool_judge.py", [str(a.render), "--beatmap", str(a.beatmap),
                                 "--out", str(cool_dir)])

    from data_learning import showrunner
    rec = showrunner.record(a.slug, a.label, interest_dir, cool_dir, a.log)
    rules = showrunner.learn()
    print(f"\n[gate] recorded {a.slug}/{a.label} (seq {rec['seq']}) and re-learned "
          f"from {rules['generated_from_n_renders']} renders\n")
    print(showrunner._fmt_report(rules))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
