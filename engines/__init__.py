"""engines — the shared capability layer for every channel.

This package is the top-of-pipeline "engine registry": reusable rendering /
media capabilities that any channel, script, or Claude session can call.
Nothing in the production pipeline imports it yet — every capability here is
strictly opt-in. The human-readable registry (including triage verdicts on
engines we deliberately did NOT integrate) lives in docs/ENGINE_REGISTRY.md.

The contract (modeled on higgsfield.maybe_animate_still)
--------------------------------------------------------
Every engine module in this package follows three rules:

1. ``available() -> bool`` is OFFLINE and DETERMINISTIC. It checks that
   dependencies import, binaries are on PATH, and model files are present
   with a valid checksum. It never touches the network. Provisioning is a
   separate, explicit step: ``python -m engines install <engine>``.

2. Best-effort entry points are named ``maybe_*`` and return a result on
   success or ``None`` on ANY failure — they never raise into a caller. A
   renderer that calls ``maybe_parallax(...)`` and gets ``None`` simply falls
   through to its existing behavior (e.g. Ken Burns).

3. An engine never mutates repo state. Models and scratch output live under
   ``cache/`` (gitignored).

CLI (how another Claude chat discovers and drives this)
-------------------------------------------------------
    python -m engines list                 # every registered engine + status
    python -m engines info parallax        # full metadata for one engine
    python -m engines doctor [parallax]    # deterministic health checks
    python -m engines install parallax     # provision deps + pinned model
    python -m engines demo kenburns --image assets/mascot/anchor/laugh.png --out /tmp/kb.mp4
    python -m engines demo parallax --image photo.jpg --out /tmp/px.mp4
"""
from __future__ import annotations

import importlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
MODELS_DIR = CACHE_DIR / "models"

# Lifecycle states: active | experimental | deferred | rejected.
# Only engines this package can health-check or run appear here; the full
# triage (including deferred/rejected tools) is in docs/ENGINE_REGISTRY.md.
#
# kind:
#   "module"   — implemented in engines/<name>.py (runnable via the CLI)
#   "external" — pre-existing pipeline dependency; registered so `doctor`
#                can health-check it, but owned by the workflows/renderers.
REGISTRY: dict[str, dict] = {
    "still_motion": {
        "kind": "module",
        "status": "active",
        "problem": "Animate a still image (Ken Burns push in/out) so no frame "
                   "is ever frozen. Canonical implementation of the effect "
                   "that currently exists as three private copies in the "
                   "renderers (migration is Ticket E1 — NOT yet migrated).",
        "headless": True,
        "control": "python (engines.still_motion.kenburns) / CLI demo",
        "reusable": True,
        "license": "n/a (ffmpeg subprocess, stdlib only)",
        "commercial_use": True,
        "cpu_ok": True,
        "est_runtime": "~1-3 s per clip (ffmpeg zoompan)",
        "deps": ["ffmpeg on PATH"],
        "fallback": "none needed — this IS the fallback other engines fall to",
        "consumers": ["make_text_card.py:161 (maybe_kenburns)",
                      "make_explainer_stacked.py:1603 (maybe_kenburns)"],
        "failure_modes": ["corrupt input image -> ffmpeg error (raised; "
                          "callers wanting best-effort use maybe_kenburns)"],
        "sample": "python -m engines demo kenburns --image assets/mascot/anchor/laugh.png --out /tmp/kb.mp4",
    },
    "render_qa": {
        "kind": "module",
        "status": "active",
        "problem": "Catch BROKEN renders (black tail/open, freezes, A/V "
                   "drift, double-letterboxing) offline and for free, "
                   "before a channel burns a vision call or ships the "
                   "defect. Born from third-channel run 30459022509: a "
                   "solid-black final frame reached the PAID vision critic "
                   "when a $0 ffmpeg pass would have caught it.",
        "headless": True,
        "control": "python (engines.render_qa.maybe_check) / CLI demo",
        "reusable": True,
        "license": "n/a (ffmpeg subprocess, stdlib only)",
        "commercial_use": True,
        "cpu_ok": True,
        "est_runtime": "~3-8 s per clip (one full decode + 3 sampled "
                       "cropdetect windows)",
        "deps": ["ffmpeg on PATH", "ffprobe on PATH"],
        "returns": "dict {ok, problems, metrics} — the first ANALYSIS "
                   "engine; None from maybe_check means the analyzer "
                   "failed (fail-open), ok=False is a real defect verdict",
        "fallback": "none needed — callers proceed unchecked on None, "
                    "exactly as if the engine did not exist",
        "consumers": ["third_capture.clip_qa (pre-vision mechanical gate)"],
        "failure_modes": ["blurred/stylistic padding is INVISIBLE to "
                          "cropdetect (near-black bars only) — aesthetic "
                          "judgment stays with the vision critic"],
        "sample": "python -m engines demo render_qa --video output/third/clip.mp4",
    },
    "parallax": {
        "kind": "module",
        # Promoted 2026-07-10 after the 8-category benchmark (Ticket E2):
        # all photo categories rendered clean; flat art + text are refused
        # by the input suitability gate (see _suitable in parallax.py).
        # Production adoption per channel still requires a preview render.
        "status": "active",
        "gated": True,
        "problem": "2.5D depth-parallax camera move from a single still — "
                   "genuinely new capability vs. flat Ken Burns zoom.",
        "headless": True,
        "control": "python (engines.parallax.maybe_parallax) / CLI demo",
        "reusable": True,
        "license": "Apache-2.0 (Depth Anything V2 SMALL — the larger V2 "
                   "checkpoints are CC-BY-NC and must NOT be used on "
                   "monetized channels)",
        "commercial_use": True,
        "cpu_ok": True,
        "est_runtime": "~2-5 s depth inference (CPU) + ~0.05 s/frame remap",
        "deps": ["opencv-python-headless", "onnxruntime", "numpy",
                 "ffmpeg on PATH", "pinned model in cache/models/"],
        "model": {
            "name": "depth_anything_v2_small.onnx",
            "repo": "onnx-community/depth-anything-v2-small",
            "revision": "4472b7362082ad9968fee890ca0f1e5aca36b93d",
            "url": ("https://huggingface.co/onnx-community/"
                    "depth-anything-v2-small/resolve/"
                    "4472b7362082ad9968fee890ca0f1e5aca36b93d/onnx/model.onnx"),
            "sha256": "afb6a5c28f3b6bf1618c6e43f02073ef9dfdc70e937502d51603e57b0a1df10c",
            "size_bytes": 99060839,
            "input_size": 518,
        },
        "fallback": "engines.still_motion.kenburns (callers get None and fall through)",
        "consumers": [],
        "failure_modes": [
            "torn/haloed object edges on strong depth discontinuities",
            "rubber-sheet distortion on flat art, diagrams, text slides",
            "wrong depth on illustrations (trained on photos)",
        ],
        "benchmark": "python -m engines.benchmarks.parallax_bench "
                     "(promotion to active requires passing verdict — Ticket E2)",
        "sample": "python -m engines demo parallax --image photo.jpg --out /tmp/px.mp4",
        # Gated is a WAITING ROOM, not a residence (doctor finding
        # 1207ec562569: both gated engines had sat consumerless with no
        # deadline since July). By the decision date below, either a channel
        # has run the named trial and adopted it, or it demotes to
        # experimental/deferred — the honesty test fails the suite the day
        # after, so the decision cannot be skipped quietly.
        #
        # RE-DATED 2026-09-16 (with reason, same clock test_engine_registry
        # _honesty.py names — "adopt, demote, or re-date with a reason"; see
        # svg_motion's identical precedent from 2026-09-02 — and its end: it
        # was DELETED on 2026-10-03 when its re-dated deadline passed too): the
        # 2026-09-15 deadline passed with no session having actually run the
        # trial. It expired as an unrelated CI-red blocker on that day's
        # trending+explainer content PR (auto-merge.yml's own `tests` job
        # runs this suite), which is not the right context to rush the real
        # showrunner-scored A/B render this decision needs — and a fake
        # trial to clear the gate would be worse than an honest extension.
        # Extending 30 days for a session with the bandwidth to actually run
        # `python -m engines.benchmarks.parallax_bench` and the named trial.
        "decision_date": "2026-10-16",
        "trial": "preview render of one explainer story with parallax on "
                 "its photo beats (kenburns as the A side); adopt on a "
                 "showrunner score no worse than the A cut, else demote.",
    },
    "chart_race": {
        "kind": "module",
        "status": "active",
        "problem": "Animated multi-series line-chart race (graphfather "
                   "style): eased timeline, dynamic y-camera zoom, tip dots "
                   "+ de-cluttered value labels, PER-SERIES ICONS (flags / "
                   "brand LOGOS via funnel.series_icons, initials-badge "
                   "fallback), a compact key parked above the plot, "
                   "measured/wrapped title, climbing year counter, "
                   "winner tag on the end-hold, optional hook overlay. "
                   "Renders a SILENT portrait mp4 — callers mux their own "
                   "audio. First consumer: trending channel's graph_race "
                   "format (make_graph_race.py).",
        "headless": True,
        "control": "python (engines.chart_race.render / maybe_chart_race) "
                   "/ CLI demo",
        "reusable": True,
        "license": "n/a (matplotlib + ffmpeg, stdlib otherwise)",
        "commercial_use": True,
        "cpu_ok": True,
        "est_runtime": "~30-60 s per 12 s clip (matplotlib Agg frames)",
        "deps": ["matplotlib", "ffmpeg on PATH"],
        "gates": "assess(spec) scores DATA DRAMA (peak magnitude + growth "
                 "+ lead changes). Callers should refuse a spec it fails: "
                 "small, slow, flat numbers make an unwatchable chart, "
                 "and one line is not a race (MIN_SERIES=2, MIN_PEAK=50 "
                 "post-unit-normalization, MIN_SWING=3x / 1.6x with a "
                 "lead change).",
        "fallback": "none — a data video without the chart is nothing; "
                    "callers should fail the package, not degrade. Icons "
                    "DO degrade: a failed lookup draws an initials badge.",
        "consumers": ["make_graph_race.py (trending daily)"],
        "failure_modes": ["malformed spec (missing years/series) raises in "
                          "render; maybe_chart_race returns None"],
        "sample": "python -m engines demo chartrace --spec pkg.json "
                  "--out /tmp/race.mp4",
    },
    "chatterbox_tts": {
        "kind": "module",
        # 2026-10-08: the explainer's narration voice. Operator, on the voice
        # lab page, of a clone of a real LibriTTS-R narrator: "chatterbox
        # lowkey sound better then eleven labs". Free, local, no account.
        "status": "active",
        "problem": "A narration voice people cannot tell is AI, for free: "
                   "Chatterbox clones one real person (Voice 38, GLOBE, "
                   "CC0; caaleb's pick 2026-10-09) from a 10 s clip in "
                   "assets/voice/, on the runner's "
                   "CPU, and every line is listened back (whisper) before "
                   "it is used — the showrunner judges frames, not audio.",
        "headless": True,
        "control": "python (engines.chatterbox_tts.maybe_voice)",
        "reusable": True,
        "license": "MIT (Chatterbox code + weights, Resemble AI); the "
                   "channel's voice is CC0 (GLOBE / Common Voice); the lab's "
                   "LibriTTS-R voices are CC BY 4.0 and a video one of them "
                   "narrates carries chatterbox_tts.CREDIT",
        "commercial_use": True,
        "cpu_ok": True,
        "est_runtime": "see engines/chatterbox.models.json (measured on a "
                       "GitHub runner); lines already voiced come from the "
                       "TTS line cache for free",
        "deps": ["its own venv (cache/venvs/chatterbox, pinned by "
                 "engines/chatterbox.lock)", "ffmpeg on PATH",
                 "openai-whisper in the pipeline env (the listener)",
                 "pinned model in cache/models/chatterbox/"],
        "models": json.loads((Path(__file__).with_name(
            "chatterbox.models.json")).read_text())["models"],
        "fallback": "None from maybe_voice: studio_render voices the whole "
                    "video with ElevenLabs -> Speechify -> Kokoro, as before",
        "consumers": ["data_learning/studio_render.py (explainer narration)",
                      "scripts/post_stories.py (the voice credit)"],
        "failure_modes": [
            "an LLM voice can garble, skip or ad-lib a line: whisper must "
            "hear >= HEARD_MIN of its words, else redrawn with a new seed "
            "(REDRAWS), else the next engine voices the video",
            "CPU time: one narration per process, one process at a time",
        ],
        "sample": "python -m engines install chatterbox_tts && "
                  "python -m engines doctor chatterbox_tts",
    },
    # ---- external engines (owned elsewhere; registered for doctor) --------
    "lookmatch": {
        "kind": "module",
        # Born 2026-07-29 from the blind taste judge's money-goes verdict:
        # mixed-source media "never settles into one look" — the final film
        # grade cannot fix per-asset exposure/saturation spread. lookmatch
        # nudges each asset toward the house band BEFORE assembly; in-band
        # assets pass through untouched.
        "status": "active",
        "gated": True,
        "problem": "Per-asset look harmonization so photos/clips from many "
                   "sources read as one shoot, not a keyword search.",
        "headless": True,
        "control": "python (engines.lookmatch.maybe_harmonize) / CLI demo",
        "reusable": True,
        "license": "n/a (ffmpeg filters only, no models)",
        "commercial_use": True,
        "cpu_ok": True,
        "est_runtime": "~0.3 s probe per asset; re-encode only when out of band",
        "deps": ["ffmpeg + ffprobe on PATH"],
        # Explicitly empty, not missing. `gated` engines are allowed to have
        # no consumer — that is what gated MEANS — but the field has to say
        # so out loud, because a missing key reads as "nobody checked".
        "consumers": [],
        # Same waiting-room rule as parallax (doctor finding 1207ec562569).
        # RE-DATED 2026-09-16 (with reason — same "adopt, demote, or
        # re-date with a reason" clock as parallax above, and the same
        # 2026-09-15 deadline expired the same way, unresolved): a daily
        # content-authoring PR is not the right context to run a real
        # third-channel clip-slate trial. Extending 30 days.
        "decision_date": "2026-10-16",
        "trial": "harmonize one third-channel clip slate's mixed-source "
                 "media before assembly; adopt if the blind look judge "
                 "stops flagging 'never settles into one look', else demote.",
    },
    "ffmpeg": {
        "kind": "external", "status": "active",
        "problem": "All video/audio encode, filter, mux.",
        "check": {"binary": "ffmpeg"},
        "consumers": ["every renderer"],
    },
    "blender": {
        "kind": "external", "status": "active",
        "problem": "Full 3D engine (Cycles). Ships with OpenVDB volumetrics "
                   "and OpenColorIO built in — 'integrating OpenVDB/OCIO' "
                   "means using Blender features, not new dependencies.",
        "check": {"binary": "blender"},
        "consumers": ["curiosity (data_learning/longform_render.py:436)"],
    },
    "manim": {
        "kind": "external", "status": "active",
        "problem": "Mathematical/data animation.",
        "check": {"import": "manim"},
        "consumers": ["curiosity (data_learning/longform_render.py:382)"],
    },
    "kokoro": {
        "kind": "external", "status": "active",
        "problem": "Neural TTS (ONNX, CPU).",
        "check": {"import": "kokoro_onnx"},
        "consumers": ["daily", "explainer", "curiosity", "longform"],
    },
    "rembg": {
        "kind": "external", "status": "active",
        "problem": "Subject cutout / background removal (covers the SAM 2 "
                   "use case at current quality needs).",
        "check": {"import": "rembg"},
        "consumers": ["explainer scene_media", "mascot gen"],
    },
    "whisper": {
        "kind": "external", "status": "active",
        "problem": "Speech-to-text for caption timing.",
        "check": {"import": "whisper"},
        "consumers": ["caption pipeline"],
    },
    "opencv": {
        "kind": "external", "status": "active",
        "problem": "Image ops: remap/warp (parallax), and future "
                   "stabilization / motion QA. Newly available shared "
                   "dependency, initially consumed by parallax.",
        "check": {"import": "cv2"},
        "consumers": ["engines.parallax"],
    },
}


def names() -> list[str]:
    return list(REGISTRY)


def info(name: str) -> dict:
    if name not in REGISTRY:
        raise KeyError(f"unknown engine {name!r} — try: {', '.join(REGISTRY)}")
    return REGISTRY[name]


def _check_external(meta: dict) -> bool:
    chk = meta.get("check", {})
    if "binary" in chk:
        return shutil.which(chk["binary"]) is not None
    if "import" in chk:
        try:
            importlib.import_module(chk["import"])
            return True
        except Exception:
            return False
    return False


def available(name: str) -> bool:
    """Offline, deterministic availability check. Never touches the network."""
    meta = info(name)
    if meta["kind"] == "external":
        return _check_external(meta)
    mod = importlib.import_module(f"engines.{name}")
    return bool(mod.available())
