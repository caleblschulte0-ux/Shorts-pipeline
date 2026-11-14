#!/bin/bash
# THE STORYBOARD PASS: a few rough key stills of every shot, judged at phone size BEFORE any proof render.
# usage: STORY=<story> bash board3d.sh OUTDIR [KEYS]      (runs every measured pre-check too: a shot that fails one
# renders nothing). Two shots build at a time. exit = the judge's (0 pass, 2 fail, 1 no judge).
# caaleb 2026-11-13: "what would an even smarter person be doing?" -- the saffron proofs each took 40 minutes to
# show what one still shows in a minute.
set -u
OUT=$1; KEYS=${2:-4}; PY=${VBPY:-python3}; cd "$(dirname "$0")"
N=$(python3 -c "import json,os;print(len(json.load(open('../stories/'+os.environ['STORY']+'/script.json'))['lines']))")
mkdir -p "$OUT"
for n in $(seq 1 $N); do
  ( rm -rf "$OUT/s$n"; SHOT=$n KEYS=$KEYS STAGING=strict $PY -I shots.py "$OUT/s$n" 8 30 > "$OUT/s$n.log" 2>&1
    grep -E "fails|Traceback" "$OUT/s$n.log" | sed "s/^/shot $n: /" ) &
  (( n % 2 == 0 )) && wait
done; wait
JUDGE3D_BOARD=1 JUDGE3D_REJUDGE=1 python3 judge3d.py "$OUT" "$OUT/board_verdict.json"
