#!/usr/bin/env python3
"""Phase 5 controlled experiments — isolate the render-slowdown cause.

The reported symptom was RISING render time across a long run. Each
experiment tests one hypothesis:

  A  same scene 10x            -> does the orchestration loop itself degrade?
                                  (leaked images / fds / child processes)
  B  10 different scene kinds  -> expensive re-initialization or retention?
  E  assembly-only             -> is the dissolve-join / final encode the cost?

(C/D — cached vs live media — need the network gateway and are covered by the
full-render instrumentation: pro_render's performance.json separates
asset-resolution time from render time per shot.)

Verdicts are computed from the data, not eyeballed: a slope is "rising" only
when the last-3 mean exceeds the first-3 mean by >20%.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_learning import scenes
from data_learning import footage_hybrid as fh
from data_learning.perf_instrument import _capture_memory

WORK = Path("/tmp/perf_experiments")


def _trend(times: list[float]) -> str:
    if len(times) < 6:
        return "n/a"
    first = sum(times[:3]) / 3
    last = sum(times[-3:]) / 3
    ratio = last / first if first else 1.0
    return f"{'RISING' if ratio > 1.2 else 'flat'} ({ratio:.2f}x first->last)"


def experiment_a(n: int = 10) -> dict:
    """Same scene, n times. Degradation here = the loop/process leaks."""
    print(f"\n[A] same scene x{n} (tax_scene, 2.0s each)", file=sys.stderr)
    times, rss, fds = [], [], []
    for i in range(n):
        out = WORK / f"a_{i:02d}.mp4"
        t0 = time.time()
        scenes.tax_scene(out, 2.0, number="25%", label="TAX", extra=None)
        dt = time.time() - t0
        m = _capture_memory()
        times.append(dt)
        rss.append(m.rss_mb)
        fds.append(m.fd_count)
        print(f"  run {i}: {dt:5.2f}s  rss {m.rss_mb:6.1f}MB  fd {m.fd_count}",
              file=sys.stderr)
    return {"times": times, "rss_mb": rss, "fd": fds,
            "time_trend": _trend(times),
            "rss_growth_mb": rss[-1] - rss[0],
            "fd_growth": fds[-1] - fds[0]}


def experiment_b() -> dict:
    """Ten DIFFERENT scene kinds back-to-back."""
    kinds = [
        ("paycheck", scenes.paycheck_scene), ("tax", scenes.tax_scene),
        ("rent", scenes.rent_scene), ("gas", scenes.gas_scene),
        ("treadmill", scenes.treadmill_scene), ("sleep", scenes.sleep_scene),
        ("work", scenes.work_scene), ("queue", scenes.queue_scene),
        ("traffic", scenes.traffic_scene), ("hold", scenes.hold_scene),
    ]
    print(f"\n[B] {len(kinds)} different scene kinds (2.0s each)", file=sys.stderr)
    times, rss = [], []
    for i, (name, fn) in enumerate(kinds):
        out = WORK / f"b_{i:02d}_{name}.mp4"
        t0 = time.time()
        try:
            fn(out, 2.0, number="", label=name.upper(), extra=None)
        except TypeError:
            fn(out, 2.0)          # a few scenes take no number/label kwargs
        dt = time.time() - t0
        m = _capture_memory()
        times.append(dt)
        rss.append(m.rss_mb)
        print(f"  {name:10} {dt:5.2f}s  rss {m.rss_mb:6.1f}MB", file=sys.stderr)
    return {"times": times, "rss_mb": rss, "time_trend": _trend(times),
            "rss_growth_mb": rss[-1] - rss[0]}


def experiment_e() -> dict:
    """Assembly-only: dissolve-join the A-experiment clips + encode."""
    clips = sorted(WORK.glob("a_*.mp4"))
    print(f"\n[E] assembly-only: dissolve_join of {len(clips)} clips",
          file=sys.stderr)
    out = WORK / "e_joined.mp4"
    t0 = time.time()
    fh.dissolve_join(clips, out, xfade=0.6)
    join_t = time.time() - t0
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(out)], capture_output=True, text=True
    ).stdout.strip() or 0)
    print(f"  join: {join_t:5.2f}s for {dur:.1f}s of video "
          f"({join_t/max(dur,0.1):.2f}x realtime)", file=sys.stderr)
    return {"join_s": join_t, "video_s": dur,
            "multiplier": join_t / max(dur, 0.1)}


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    report = {"A_same_scene": experiment_a(),
              "B_mixed_scenes": experiment_b(),
              "E_assembly": experiment_e()}

    a, b, e = report["A_same_scene"], report["B_mixed_scenes"], report["E_assembly"]
    print("\n" + "=" * 64, file=sys.stderr)
    print("EXPERIMENT VERDICTS", file=sys.stderr)
    print(f"  A same-scene loop : {a['time_trend']}, "
          f"rss {a['rss_growth_mb']:+.1f}MB, fd {a['fd_growth']:+d}",
          file=sys.stderr)
    print(f"  B mixed scenes    : {b['time_trend']}, "
          f"rss {b['rss_growth_mb']:+.1f}MB", file=sys.stderr)
    print(f"  E assembly        : {e['multiplier']:.2f}x realtime "
          f"for {e['video_s']:.0f}s", file=sys.stderr)
    print("=" * 64, file=sys.stderr)

    (WORK / "report.json").write_text(json.dumps(report, indent=2))
    print(f"report -> {WORK / 'report.json'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
