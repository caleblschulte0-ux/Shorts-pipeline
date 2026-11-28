#!/bin/bash
# every 10th frame at test size, tiled into one sheet. usage: testpass.sh OUTDIR [SPP] [PCT]
set -e
OUT=${1:?outdir}; SPP=${2:-16}; PCT=${3:-45}
HERE=$(cd "$(dirname "$0")" && pwd); PY=${VBPY:-/tmp/claude-0/-home-claude-shorts-pipeline/98be0241-5f3b-5b37-8fd0-e69535d5e365/scratchpad/vbpy/bin/python}
STEP=10 "$PY" -I "$HERE/checkout.py" "$OUT" "$SPP" "$PCT" 2>&1 | grep -v "^Fra:"
python3 "$HERE/sheet.py" "$OUT" "$OUT/sheet.jpg" 6
echo "SHEET $OUT/sheet.jpg"
