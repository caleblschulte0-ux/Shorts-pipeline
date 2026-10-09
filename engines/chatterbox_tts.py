"""Chatterbox: a free, local narration voice cloned from a real person.

Operator, 2026-10-08: ElevenLabs is hard to justify paying for, yet the
voice is "the only difference between one of our videos and a half as
interesting video"; a voice people can recognise as AI "is cooked"; and
recording their own voice "defeats the whole point of it being autonomous".
On the voice lab page, a Chatterbox clone of a real LibriTTS-R narrator
"lowkey sound[s] better than ElevenLabs".

So this engine clones one of five real narrators (LibriTTS-R, CC BY 4.0,
`assets/voice/`) with Resemble AI's Chatterbox (MIT), on the runner's CPU,
for nothing.

Isolation. Chatterbox pins torch 2.6, numpy<2 and transformers 5.2, which
the pipeline's own environment must not inherit. It lives in its own venv
(`cache/venvs/chatterbox`, exact versions in `engines/chatterbox.lock`) and
runs as a subprocess (`engines/_chatterbox_worker.py`) with a scrubbed
environment: no API key, token or secret is passed to it, and it runs with
the Hugging Face hub offline, reading only the pinned, hash-checked files.

It cannot be heard by the showrunner, which judges frames. An LLM-based
voice can garble or ad-lib a line, so every line is LISTENED to (whisper,
already in the pipeline) and must say what it was asked to say, or it is
redrawn with a new seed; a line that still fails makes `maybe_voice` return
None and the caller voices the whole video with its next engine.

    python -m engines install chatterbox_tts
    python -m engines doctor chatterbox_tts
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from engines import CACHE_DIR, MODELS_DIR, REGISTRY, ROOT

META = REGISTRY["chatterbox_tts"]
VENV = CACHE_DIR / "venvs" / "chatterbox"
VENV_PY = VENV / "bin" / "python"
LOCK = Path(__file__).with_name("chatterbox.lock")
WORKER = Path(__file__).with_name("_chatterbox_worker.py")
VOICE_DIR = ROOT / "assets" / "voice"

#: The narrators on the voice lab page, by the number caaleb sees there,
#: each a 10 s clip in assets/voice/ (assets/voice/README.md says where
#: every one came from).
VOICES = {"1": "libritts_r_3000", "2": "libritts_r_2086", "3": "libritts_r_2902",
          "4": "libritts_r_3170", "5": "libritts_r_6319", "38": "globe_S_001818"}
#: caaleb, 2026-10-09, of Voice 38 on the full model after the finals on two
#: real stories: "make that the new voice of the channel". One voice for
#: every video (2026-10-08: never rotate it, never match it to a topic).
DEFAULT_VOICE = "38"
#: The full model, with its energy dial where the finals were rendered.
#: Turbo voices five lines in ~80 s on a runner, the full model in ~270 s
#: (engines/chatterbox.models.json); the repo variable can still pick.
DEFAULT_MODEL = "full"
FULL_STYLE = {"exaggeration": 0.75, "cfg_weight": 0.35}
#: A run that has spent this long in the full model finishes on Turbo in
#: the SAME voice, so a long day cannot push the explainer job past its
#: timeout (the full model is ~3x slower). Minutes, repo variable
#: CHATTERBOX_FULL_BUDGET_MIN.
FULL_BUDGET_MIN = 75.0
_FULL_SPENT_S = 0.0

#: CC BY 4.0 asks for credit wherever a LibriTTS-R voice is used. GLOBE
#: (Common Voice) is CC0: nothing to credit.
CREDIT = ("Narration voice based on the LibriTTS-R corpus (Koizumi et al., "
          "2023), licensed under Creative Commons: By Attribution 4.0 "
          "(creativecommons.org/licenses/by/4.0/). Voice model: Chatterbox "
          "by Resemble AI (MIT).")


def credit_for(stem: str) -> str:
    """The description credit a voice's licence asks for, by its clip's stem."""
    return CREDIT if str(stem).startswith("libritts_r_") else ""

#: A line must say at least this share of its words, in order, as heard by
#: whisper. Base.en mishears the odd word; an ad-lib, a dropped clause or a
#: stutter loop is far below it.
HEARD_MIN = 0.75
#: Natural speech, before the registry tempo: words per second.
RATE_MIN, RATE_MAX = 1.3, 4.6
REDRAWS = 2
_LISTENER = None
LAST_FAILURE: str | None = None


def voice_ref(voice: str | None = None) -> Path:
    v = str(voice or os.environ.get("CHATTERBOX_VOICE") or DEFAULT_VOICE).strip()
    p = VOICE_DIR / f"{VOICES.get(v, v)}.ogg"
    return p if p.is_file() else VOICE_DIR / f"{VOICES[DEFAULT_VOICE]}.ogg"


def _budget_s() -> float:
    try:
        return 60.0 * float(os.environ.get("CHATTERBOX_FULL_BUDGET_MIN") or FULL_BUDGET_MIN)
    except ValueError:
        return 60.0 * FULL_BUDGET_MIN


def model_name(model: str | None = None) -> str:
    m = str(model or os.environ.get("CHATTERBOX_MODEL") or DEFAULT_MODEL).strip()
    m = m if m in META["models"] else DEFAULT_MODEL
    if m == "full" and model is None and _FULL_SPENT_S >= _budget_s():
        try:
            if model_verified("turbo"):
                return "turbo"             # same voice, three times faster
        except Exception:  # noqa: BLE001
            pass
    return m


def model_dir(model: str | None = None) -> Path:
    spec = META["models"][model_name(model)]
    return MODELS_DIR / "chatterbox" / f"{model_name(model)}-{spec['revision'][:12]}"


def _stamp(model: str) -> Path:
    return model_dir(model) / ".sha256.ok"


def model_verified(model: str | None = None) -> bool:
    """Every pinned file present at its exact size; SHA-256 checked once and
    stamped, so doctor stays fast afterwards."""
    m = model_name(model)
    d, files = model_dir(m), META["models"][m]["files"]
    for rel, f in files.items():
        p = d / rel
        if not p.is_file() or p.stat().st_size != f["bytes"]:
            return False
    if _stamp(m).is_file():
        return True
    for rel, f in files.items():
        if hashlib.sha256((d / rel).read_bytes()).hexdigest() != f["sha256"]:
            return False
    _stamp(m).write_text("ok\n")
    return True


def _venv_ok() -> bool:
    stamp = VENV / ".lock.sha256"
    want = hashlib.sha256(LOCK.read_bytes()).hexdigest() if LOCK.is_file() else ""
    return (VENV_PY.is_file() and stamp.is_file()
            and stamp.read_text().strip() == want)


def available(model: str | None = None) -> bool:
    """Offline and deterministic: venv built from the current lock, pinned
    model verified, reference voice present."""
    try:
        return _venv_ok() and model_verified(model) and voice_ref().is_file()
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------- provision
def install(model: str | None = None) -> bool:
    """Build the venv from the lock and fetch the pinned model. The only
    network this engine ever touches."""
    m = model_name(model)
    for extra in (["turbo"] if m == "full" else []):   # the budget's fallback
        if not _fetch(extra):
            print("[chatterbox] Turbo fallback not fetched; a long run stays on full")
    if not _venv_ok() and not _build_venv():
        return False
    if not _fetch(m):
        return False
    try:                                   # the listener every line must pass
        import whisper
        whisper.load_model(os.environ.get("CHATTERBOX_LISTENER", "base.en"))
    except Exception as e:  # noqa: BLE001
        print(f"[chatterbox] listener not fetched ({e}); lines will fail closed")
    return available(m)


def _build_venv() -> bool:
    if not _venv_ok():
        print(f"[chatterbox] building venv {VENV}")
        subprocess.run([sys.executable, "-m", "venv", "--clear", str(VENV)], check=True)
        pip = [str(VENV_PY), "-m", "pip", "install", "--quiet",
               "--disable-pip-version-check"]
        subprocess.run(pip + ["--upgrade", "pip"], check=True)
        r = subprocess.run(pip + ["--no-cache-dir", "--no-deps", "-r", str(LOCK),
                                  "--extra-index-url",
                                  "https://download.pytorch.org/whl/cpu"])
        if r.returncode != 0:
            print("[chatterbox] venv install failed")
            return False
        (VENV / ".lock.sha256").write_text(
            hashlib.sha256(LOCK.read_bytes()).hexdigest() + "\n")
    return True


def _fetch(m: str) -> bool:
    """The pinned weights of one model, verified, or False."""
    if not _venv_ok() and not _build_venv():
        return False
    if not model_verified(m):
        spec = META["models"][m]
        d = model_dir(m)
        d.mkdir(parents=True, exist_ok=True)
        code = ("import sys; from huggingface_hub import snapshot_download as s; "
                "s(repo_id=sys.argv[1], revision=sys.argv[2], local_dir=sys.argv[3], "
                "allow_patterns=sys.argv[4:])")
        print(f"[chatterbox] downloading {spec['repo']}@{spec['revision'][:12]}")
        r = subprocess.run([str(VENV_PY), "-I", "-c", code, spec["repo"],
                            spec["revision"], str(d), *spec["files"]],
                           env=_worker_env(offline=False))
        _stamp(m).unlink(missing_ok=True)
        if r.returncode != 0 or not model_verified(m):
            print("[chatterbox] model download failed or did not match its "
                  "pinned SHA-256 — refusing it")
            return False
    return True


# ------------------------------------------------------------------ voicing
def _worker_env(offline: bool = True) -> dict:
    """Only what a CPU model needs. Nothing from the job's secrets."""
    env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "TMPDIR")
           if k in os.environ}
    env["HOME"] = str(CACHE_DIR / "chatterbox-home")
    env["OMP_NUM_THREADS"] = env["MKL_NUM_THREADS"] = str(_threads())
    env["TOKENIZERS_PARALLELISM"] = "false"
    if offline:
        env["HF_HUB_OFFLINE"] = env["TRANSFORMERS_OFFLINE"] = "1"
    return env


def _threads() -> int:
    return max(1, min(8, os.cpu_count() or 4))


class _OneAtATime:
    """Parallel renders share the runner's CPU; two Chatterbox processes
    would each take twice as long and hold twice the memory."""

    def __enter__(self):
        import fcntl
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.fh = open(CACHE_DIR / "chatterbox.lock", "w")
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        import fcntl
        fcntl.flock(self.fh, fcntl.LOCK_UN)
        self.fh.close()
        return False


def _seed(text: str, attempt: int) -> int:
    return int(hashlib.sha256(f"{attempt}\0{text}".encode()).hexdigest()[:8], 16)


def _run_worker(items: list[tuple[str, Path, int]], model: str, ref: Path,
                timeout: float) -> bool:
    # Absolute everywhere: the worker runs with cwd=job_dir, so a relative
    # work dir would resolve twice (found by the voice-preview run).
    items = [(t, Path(o).resolve(), s) for t, o, s in items]
    ref = Path(ref).resolve()
    job_dir = items[0][1].parent
    job = job_dir / f"chatterbox_job_{os.getpid()}.json"
    raw = [(t, o.with_suffix(".cb.wav"), s) for t, o, s in items]
    job.write_text(json.dumps({
        "model": model, "ckpt": str(model_dir(model)), "ref": str(ref),
        "threads": _threads(), **(FULL_STYLE if model == "full" else {}),
        "lines": [{"text": t, "out": str(r), "seed": s} for t, r, s in raw]}))
    t0 = time.time()
    with _OneAtATime():
        try:
            r = subprocess.run([str(VENV_PY), "-I", str(WORKER), str(job)],
                               env=_worker_env(), capture_output=True, text=True,
                               timeout=timeout, cwd=str(job_dir))
        except subprocess.TimeoutExpired:
            _fail(f"timed out after {timeout:.0f}s")
            return False
    job.unlink(missing_ok=True)
    if model == "full":
        global _FULL_SPENT_S
        _FULL_SPENT_S += time.time() - t0
    if r.returncode != 0:
        _fail(f"worker exit {r.returncode}: {(r.stderr or '')[-300:]}")
        return False
    for _t, out, _s in items:
        _trim(out.with_suffix(".cb.wav"), out)
    print(f"[tts] chatterbox {model}: {len(items)} lines in "
          f"{time.time() - t0:.0f}s", flush=True)
    return True


def _trim(src: Path, dst: Path) -> None:
    """Leading and trailing silence off (the caller adds its own breath),
    as 24kHz 16-bit mono — the rate the narration mix assumes."""
    cut = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
                    "-af", f"{cut},areverse,{cut},areverse",
                    "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
                   check=True)
    src.unlink(missing_ok=True)


def _words(text: str, normalize) -> list[str]:
    t = normalize(text) if normalize else text
    return re.findall(r"[a-z0-9']+", t.lower().replace("-", " "))


def heard(wav: Path, text: str, normalize=None) -> tuple[bool, str]:
    """Does this line SAY its text? (ok, why). The listener is whisper base.en
    on CPU; its digits are passed through the same `normalize` the text was,
    so 'fifty' and '50' agree."""
    global _LISTENER
    try:
        import wave
        with wave.open(str(wav), "rb") as w:     # _trim writes 16-bit PCM
            secs = w.getnframes() / float(w.getframerate())
    except Exception as e:  # noqa: BLE001
        return False, f"unreadable audio: {e}"
    want = _words(text, normalize)
    if not want:
        return False, "empty line"
    rate = len(want) / max(secs, 0.01)
    if not RATE_MIN <= rate <= RATE_MAX:
        return False, f"{rate:.1f} words/s over {secs:.1f}s"
    try:
        import whisper
        if _LISTENER is None:
            _LISTENER = whisper.load_model(os.environ.get("CHATTERBOX_LISTENER", "base.en"))
        got = _LISTENER.transcribe(str(wav), language="en", fp16=False,
                                   temperature=0.0)["text"]
    except Exception as e:  # noqa: BLE001
        return False, f"listener unavailable: {str(e)[:120]}"
    have = _words(got, normalize)
    score = difflib.SequenceMatcher(None, want, have, autojunk=False).ratio()
    if score < HEARD_MIN:
        return False, f"said {got.strip()[:80]!r} ({score:.2f})"
    return True, f"{score:.2f}"


def _fail(why: str) -> None:
    global LAST_FAILURE
    LAST_FAILURE = why
    print(f"[tts] chatterbox failed: {why}", file=sys.stderr, flush=True)


def maybe_voice(texts: list[str], outs: list[Path], *, voice: str | None = None,
                model: str | None = None, normalize=None,
                timeout: float = 1800.0) -> list[Path] | None:
    """Voice every line into its `outs` path (24kHz mono WAV), each one
    listened to. The list of paths, or None on ANY failure — never raises."""
    global LAST_FAILURE
    LAST_FAILURE = None
    try:
        m = model_name(model)
        if not texts or len(texts) != len(outs):
            _fail("no lines")
            return None
        if not available(m):
            _fail("not installed (python -m engines install chatterbox_tts)")
            return None
        ref = voice_ref(voice)
        todo = list(range(len(texts)))
        for attempt in range(REDRAWS + 1):
            if not _run_worker([(texts[i], Path(outs[i]), _seed(texts[i], attempt))
                                for i in todo], m, ref, timeout):
                return None
            bad = []
            for i in todo:
                ok, why = heard(Path(outs[i]), texts[i], normalize)
                if not ok:
                    print(f"[tts] chatterbox line {i} redraw: {why}",
                          file=sys.stderr, flush=True)
                    bad.append((i, why))
            todo = [i for i, _ in bad]
            if not todo:
                return [Path(o) for o in outs]
            if any(w.startswith("listener unavailable") for _, w in bad):
                break
        _fail(f"line {bad[0][0]} would not come out right: {bad[0][1]}")
        return None
    except Exception as e:  # noqa: BLE001
        _fail(f"{type(e).__name__}: {str(e)[:200]}")
        return None
