"""vod_miner — find moments in a stream VOD that nobody clipped.

Clip discovery is clipper-dependent: we only ever see the moments a human
decided to clip. On a thin day that starves the slate — 2026-07-31 the
third channel inspected four candidates, all genuinely weak, and posted
one video. The good moments in those same streams were invisible to us
because no clipper cut them.

This mines the NEIGHBOURHOOD of a clip we already have. A Twitch clip
carries its parent VOD id + offset (helix only), so a few minutes either
side is one cheap, bounded download — and the payoff a clipper missed is
very often 90 seconds after the one they caught.

Deliberately NOT full VOD mining. Transcribing hours of stream costs
~1x realtime on a CI runner; that belongs in a separate pre-miner job
(see docs/MEDIA_ACQUISITION.md). This is the affordable half: one extra
download per anchor, moments found by a cheap motion pass, and each
candidate extracted as a short clip so everything downstream — whisper,
the content gate, render, QA — treats it exactly like a normal clip.

    from funnel import vod_miner
    extra = vod_miner.maybe_mine(clip_record, work)   # [] on any failure

Contract: `maybe_mine` returns a (possibly empty) list and NEVER raises.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

# A mined candidate must never be mistaken for a clipper's work: the URL
# scheme is synthetic and carries its provenance. Nothing downstream may
# treat it as a real twitch.tv/clip link.
SCHEME = "vodmine"


def _dur(path: Path) -> float:
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)], text=True, timeout=30)
        return float(out.strip() or 0)
    except Exception:  # noqa: BLE001
        return 0.0


MIN_BYTES = 10_000


def _usable(p: Path) -> bool:
    """A previously-extracted moment is only reusable if it is WHOLE.

    `ffmpeg -y` creates the destination immediately, so a timeout or a
    non-zero exit leaves a truncated file with no moov atom behind. The
    caller short-circuits on `dest.exists()`, so without this that corpse
    is handed downstream as a valid candidate: preflight rejects it, it
    gets a permanent `rejected-vodmine://...` blocklist entry, and a slot
    attempt is burned — every time, because the bad file is still there."""
    try:
        return p.exists() and p.stat().st_size > MIN_BYTES and _dur(p) > 1.0
    except Exception:  # noqa: BLE001
        return False


def _extract(src: Path, out: Path, start: float, length: float) -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}",
             "-t", f"{length:.2f}", "-i", str(src),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", str(out)], check=True, timeout=180)
        if _usable(out):
            return True
    except Exception:  # noqa: BLE001
        pass
    # never leave a partial file behind for the exists() short-circuit
    try:
        out.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass
    return False


def maybe_mine(clip: dict, work, *, span: float = 180.0, n: int = 3,
               moment_s: float = 40.0, min_gap: float = 25.0) -> list[dict]:
    """Mine up to `n` unclipped moments from the VOD around `clip`.

    `clip` is a discovery record; it must carry helix coordinates
    (`video_id` + `vod_offset`) or there is nothing to anchor on and this
    returns []. Never raises — supply is best-effort by definition.

    Each returned candidate is a normal-looking discovery record whose
    `path` is an already-extracted short mp4, so the caller skips the
    download step and everything downstream is unchanged. `views` is
    inherited from the anchor as a velocity proxy: the moment itself has
    no view count (nobody clipped it), and the ranker needs a number.
    That inheritance is why a mined candidate must still clear the same
    transcript-aware content gate as any other — its provenance gives it
    no credit.
    """
    try:
        from third_capture import clip_edit, auto_edit
        work = Path(work)
        vid, off = clip.get("video_id"), clip.get("vod_offset")
        if not vid or off is None:
            return []
        nb = clip_edit.maybe_vod_window(clip, work, before=span, after=span)
        if not nb:
            return []
        nb_path = Path(nb["path"])
        dur = _dur(nb_path)
        if dur < moment_s * 2:
            return []

        # Cheap motion pass — no whisper here. Whisper only ever runs on
        # the SHORT extracted moment, downstream, once per surviving
        # candidate. Motion is weak on talking-head content; that is
        # acceptable because the content gate is the real judge and a
        # miss costs one wasted extraction, not a bad post.
        motion = auto_edit.motion_energy(nb_path)
        if not motion:
            return []
        peaks = auto_edit.energy_peaks(motion, [], dur,
                                       n=n + 2, min_gap=min_gap)
        if not peaks:
            return []
        # RANK BY STRENGTH, NOT BY CLOCK. energy_peaks selects the top
        # n+2 by energy and then returns them `sorted(key=t)` — the rank
        # is discarded. We over-fetch precisely so the anchor-overlap
        # filter has slack, but iterating in TIME order and breaking at n
        # keeps whichever survivors happen to come first in the window and
        # throws away the strongest moment the motion pass actually found.
        # Re-attach the energy we already have and mine the best ones.
        _e = {round(t, 2): v for t, v in motion}

        def _strength(p) -> float:
            t = p[0]
            return max((v for k, v in _e.items() if abs(k - t) <= 0.5),
                       default=0.0)
        peaks = sorted(peaks, key=_strength, reverse=True)

        # Never re-surface the anchor's own window — we already have that
        # clip, and a near-duplicate upload is the one unforgivable bug.
        anchor_t = float(nb.get("clip_offset_s") or 0.0)
        anchor_len = float(clip.get("duration") or 30.0)
        out: list[dict] = []
        for t_peak, _ws, _we in peaks:
            if anchor_t - min_gap <= t_peak <= anchor_t + anchor_len + min_gap:
                continue
            start = max(0.0, t_peak - moment_s * 0.4)
            if start + moment_s > dur:
                start = max(0.0, dur - moment_s)
            # absolute offset within the VOD, so the record is honest
            # about where this came from and dedupe can key on it
            abs_off = float(nb.get("vod_start_s") or 0.0) + start
            # NAME THE FILE BY THE ABSOLUTE OFFSET, NOT THE RELATIVE ONE.
            # `start` is relative to the neighbourhood window and is
            # clamped to canonical values (0.0, dur - moment_s), so two
            # anchors from the SAME VOD at different vod_offsets collide
            # on int(start) very readily. `work` is shared across every
            # slot and retry in the run, so the second anchor's
            # dest.exists() was true and it silently reused the FIRST
            # anchor's bytes while stamping its own abs_off — two distinct
            # vodmine:// dedupe keys pointing at one video. posted_keys,
            # the final dedupe guard and _audit_dupes all key on the URL,
            # so none of them could see it: a duplicate upload invisible
            # to every guard in the channel.
            dest = work / f"mined_{vid}_{int(abs_off)}.mp4"
            if not _usable(dest) and not _extract(nb_path, dest, start,
                                                  moment_s):
                continue
            out.append({
                "url": f"{SCHEME}://{vid}/{int(abs_off)}",
                "channel": clip.get("channel", ""),
                "platform": clip.get("platform", "twitch"),
                # inherited proxy — see docstring
                "views": int(clip.get("views") or 0),
                "title": "",          # no clipper title; the brain writes one
                "clipper": "vod-mined",
                "path": str(dest),
                "duration": moment_s,
                "video_id": vid,
                "vod_offset": abs_off,
                "mined": True,
                "mined_from": clip.get("url", ""),
                "age_h": clip.get("age_h"),
            })
            if len(out) >= n:
                break
        if out:
            print(f"[vodmine] {clip.get('channel', '?')}: {len(out)} "
                  f"unclipped moment(s) from VOD {vid}", flush=True)
        return out
    except Exception as e:  # noqa: BLE001 — supply is best-effort
        print(f"[vodmine] failed ({type(e).__name__}: {e}) — "
              "caller keeps its normal candidates", flush=True)
        return []


def is_mined(url: str) -> bool:
    """True for a synthetic mined URL. Callers that treat clip URLs as
    public links (credit lines, source_url in the posted log) must check
    this — a vodmine:// URL is not something a viewer can open."""
    return str(url or "").startswith(f"{SCHEME}://")
