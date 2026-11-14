#!/bin/bash
# the full render: 240 frames at 60% 24 spp under a lock, then post, sheet, 2 fps contact sheet, copy to project files.
set -e
OUT=${1:?outdir}; SPP=${2:-24}; PCT=${3:-60}; DEST=${DEST:-/mnt/project-files/shorts/3d/scene1}; NAME=${NAME:-checkout3d_v6}
HERE=$(cd "$(dirname "$0")" && pwd); PY=${VBPY:-/tmp/claude-0/-home-claude-shorts-pipeline/98be0241-5f3b-5b37-8fd0-e69535d5e365/scratchpad/vbpy/bin/python}
mkdir -p "$OUT"; exec 9>"$OUT/.lock"; flock -n 9 || { echo "another full render holds $OUT/.lock"; exit 1; }
"$PY" -I "$HERE/checkout.py" "$OUT" "$SPP" "$PCT" 2>&1 | grep -v "^Fra:"
bash "$HERE/post.sh" "$OUT" "$OUT/$NAME.mp4"
python3 "$HERE/sheet.py" "$OUT" "$OUT/${NAME}_sheet.jpg" 6 10
python3 "$HERE/sheet.py" "$OUT" "$OUT/${NAME}_2fps.jpg" 8 12
mkdir -p "$DEST"; cp "$OUT/$NAME.mp4" "$OUT/${NAME}_sheet.jpg" "$OUT/${NAME}_2fps.jpg" "$DEST/"
echo "DONE $DEST/$NAME.mp4"
