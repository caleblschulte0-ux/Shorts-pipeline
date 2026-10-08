"""The real narration path on real stories, outside the explainer's posting
queue: story.build -> st.sentences() -> studio_render.synth_narration, with
the Chatterbox engine installed exactly as explainer.yml installs it."""
import json, sys, time, subprocess
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "data_learning"))
from data_learning import studio_render as R
from data_learning import story
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
cfg = json.loads((REPO / "data_learning" / "niche.config.json").read_text())
rep = {}
for slug in sys.argv[2:]:
    sc = next(s for s in cfg["stories"] if s["slug"] == slug)
    work = out / f"_w_{slug}"; work.mkdir(exist_ok=True)
    st = story.build(sc, cfg, work, REPO)
    sents = st.sentences()
    t0 = time.time()
    nar, windows = R.synth_narration(sents, work, "am_fenrir")
    rep[slug] = {"seconds_to_voice": round(time.time() - t0, 1), "tts": dict(R.TTS_USED),
                 "lines": [R._tts_text(s) for s in sents],
                 "windows": [[round(a, 2), round(b, 2)] for a, b in windows]}
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(nar), "-b:a", "160k",
                    str(out / f"{slug}.mp3")], check=True)
    print(json.dumps({slug: rep[slug]}, indent=1), flush=True)
(out / "narration_test.json").write_text(json.dumps(rep, indent=1))
