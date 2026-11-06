#!/bin/bash
# frames -> 1080x1920 24 fps mp4: lanczos 2x up, 1.00->1.06 push-in, down to 1080x1920, deeper blacks, slight sharpen,
# CRF 18, a synthesised quiet store-ambience bed (no commercial music). usage: post.sh FRAMEDIR OUT.mp4
set -e
IN=${1:?framedir}; OUT=${2:?out.mp4}; N=$(ls "$IN"/f*.png | wc -l)
AMB="anoisesrc=color=pink:amplitude=0.018:seed=7,lowpass=f=900,highpass=f=80,aformat=channel_layouts=stereo"
ffmpeg -y -loglevel error -framerate 24 -pattern_type glob -i "$IN/f*.png" \
  -f lavfi -t $(python3 -c "print($N/24)") -i "$AMB" \
  -filter_complex "[0:v]scale=2160:3840:flags=lanczos,zoompan=z='1+0.06*on/$N':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=2160x3840:fps=24,scale=1080:1920:flags=lanczos,curves=all='0/0 0.2/0.155 0.8/0.82 1/1',eq=saturation=0.95,vignette=angle=PI/5:mode=forward,unsharp=5:5:0.4,format=yuv420p[v];[1:a]volume=0.4[a]" \
  -map "[v]" -map "[a]" -c:v libx264 -preset slow -crf 18 -r 24 -c:a aac -b:a 96k -shortest "$OUT"
echo "POST $OUT"
