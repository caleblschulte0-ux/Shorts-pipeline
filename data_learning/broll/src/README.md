# Drop bottom-strip footage here

Put any long power-washing (or other oddly-satisfying process) video(s) in
this folder as .mp4/.mov/.webm, then run:

    python -m data_learning.build_broll

It will normalize + stitch them into ../satisfying.mp4, which the studio
renderer samples a rotating segment from each render (so it never obviously
repeats). One long video is ideal.

No file here? build_broll falls back to PEXELS_API_KEY / PIXABAY_API_KEY
(free keys — real pressure-washing clips), then Coverr (no key, limited).
