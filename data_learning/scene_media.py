"""Cinematic scene imagery for the data-explainer channel (best-effort).

Every scene (the hook, and each segment) gets a bold, attention-grabbing image
behind the animated data. Order of preference:

  1. AI generation via Gemini (free-tier, vertical 9:16) — bold cinematic look.
  2. A license-safe stock photo (Wikipedia/Commons via topic_media).
  3. None — the renderer falls back to a designed gradient.

All failures (no key, quota, network) degrade to the next option and ultimately
to None, so a scene always renders. Images cache under state/scene_images/.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from data_learning import hook_media           # noqa: E402 — stock fetch + query helpers

CACHE_DIR = REPO / "state" / "scene_images"


def _prompt(subject: str, context: str = "") -> str:
    """Bold-cinematic art direction. Gemini appends its own
    'vertical 9:16, no text' suffix, so we focus on look + subject."""
    ctx = f" Context: {context.strip()}." if context.strip() else ""
    return (
        f"A bold, cinematic poster-style image representing {subject}.{ctx} "
        "Dramatic moody lighting, vibrant high-contrast color grade, shallow "
        "depth of field, epic and eye-catching, editorial magazine quality, "
        "strong central subject, vertical composition. No text or numbers."
    )


_DIAG_DONE = False


def _diag_once():
    """Log, once per run, what image models this Gemini key actually exposes —
    so we can tell 'not enabled' from 'quota' from 'reachable'."""
    global _DIAG_DONE
    if _DIAG_DONE:
        return
    _DIAG_DONE = True
    try:
        import gemini_images
        print(f"[scene][diag] gemini enabled={gemini_images.enabled()}", flush=True)
        avail = gemini_images._available_models()
        img = sorted(m for m in avail if "image" in m.lower() or "imagen" in m.lower())
        print(f"[scene][diag] image-capable models visible ({len(img)}): {img}",
              flush=True)
        free = [m for m in gemini_images.FREE_IMAGE_MODELS if (not avail or m in avail)]
        print(f"[scene][diag] usable FREE image models: {free}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[scene][diag] probe error: {e}", flush=True)


def _gen_pollinations(subject: str, dest: Path, context: str = "") -> Path | None:
    """Generate a bold-cinematic image via Pollinations.ai — FREE, no API key,
    just an HTTP GET. Deterministic per prompt (seeded) so re-renders are stable.
    Best-effort: any failure returns None and the caller falls back."""
    import hashlib
    import ssl
    import urllib.parse
    import urllib.request
    try:
        prompt = _prompt(subject, context)
        seed = int(hashlib.sha1(prompt.encode()).hexdigest()[:8], 16)
        url = ("https://image.pollinations.ai/prompt/"
               + urllib.parse.quote(prompt)
               + f"?width=1080&height=1920&nologo=true&model=flux&seed={seed}")
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "shorts-pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
            data = r.read()
        if len(data) < 4096:
            return None
        dest.write_bytes(data)
        from PIL import Image
        with Image.open(dest) as im:
            if min(im.size) < 400:
                dest.unlink(missing_ok=True)
                return None
        print(f"[scene] pollinations image OK -> {dest.name}", flush=True)
        return dest
    except Exception as e:  # noqa: BLE001 — never block a render
        print(f"[scene] pollinations skipped: {e}", flush=True)
        return None


def _gen_ai(subject: str, dest: Path, context: str = "") -> Path | None:
    try:
        import gemini_images
        _diag_once()
        if not gemini_images.enabled():
            return None
        p = gemini_images.generate_image(_prompt(subject, context), dest)
        if p and Path(p).exists() and Path(p).stat().st_size > 2048:
            print(f"[scene] AI image OK -> {Path(p).name}", flush=True)
            return Path(p)
        print("[scene] AI image returned nothing — falling back to stock", flush=True)
    except Exception as e:  # noqa: BLE001 — never block a render
        print(f"[scene] AI image skipped: {e}", flush=True)
    return None


def scene_image(subject: str, slug: str, tag: str, *, context: str = "",
                allow_stock: bool = True, cache_dir: Path = CACHE_DIR) -> Path | None:
    """Return a cached cinematic image for `subject` (AI → stock → None).
    `tag` distinguishes scenes within a story (e.g. 'hook', 'seg01')."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in f"{slug}__{tag}")
    dest = cache_dir / f"{safe}.png"
    if dest.exists() and dest.stat().st_size > 2048:
        return dest
    if (subject or "").strip():
        # Free AI first (Pollinations), then paid Gemini if ever enabled.
        poll = _gen_pollinations(subject, dest, context)
        if poll:
            return poll
        ai = _gen_ai(subject, dest, context)
        if ai:
            return ai
    if allow_stock:
        try:
            import topic_media
            import entity_media
            cands, seen = [], set()
            for q in [subject] + [w for w in (subject or "").split() if len(w) > 3]:
                q = q.strip()
                if q and q.lower() not in seen:
                    seen.add(q.lower())
                    cands.append(q)
            for q in cands[:4]:
                urls = topic_media.search(q, context) or []
                for url in urls[:4]:
                    try:
                        if entity_media.url_is_image(url):
                            p = hook_media._download(url, cache_dir)
                            if p:
                                return p
                    except Exception:  # noqa: BLE001
                        continue
        except Exception:  # noqa: BLE001
            pass
    return None


CUTOUT_DIR = REPO / "state" / "cutouts"


def _pollinations_raw(prompt: str, seed: int, size: int = 768):
    """Return a PIL RGB image from Pollinations, or None."""
    import io
    import ssl
    import urllib.parse
    import urllib.request
    try:
        url = ("https://image.pollinations.ai/prompt/"
               + urllib.parse.quote(prompt)
               + f"?width={size}&height={size}&nologo=true&model=flux&seed={seed}")
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "shorts-pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
            data = r.read()
        if len(data) < 4096:
            return None
        from PIL import Image
        return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:  # noqa: BLE001
        print(f"[scene] cutout gen skipped: {e}", flush=True)
        return None


def _chroma_cut(img):
    """Green-screen key (numpy): make the chroma-green background transparent,
    despill, crop to the subject. Returns an RGBA PIL image or None."""
    try:
        import numpy as np
        from PIL import Image
        a = np.asarray(img.convert("RGB")).astype(np.int16)
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        green = (g > 90) & (g > r * 1.2) & (g > b * 1.2)
        alpha = np.where(green, 0, 255).astype(np.uint8)
        rgb = a.astype(np.uint8).copy()
        # despill: pull green down toward the red/blue average on kept pixels
        keep = ~green
        avg = ((r + b) // 2).astype(np.uint8)
        gg = rgb[..., 1]
        spill = keep & (gg > avg)
        gg[spill] = avg[spill]
        rgb[..., 1] = gg
        out = np.dstack([rgb, alpha])
        im = Image.fromarray(out, "RGBA")
        bbox = im.getbbox()
        if not bbox:
            return None
        im = im.crop(bbox)
        if min(im.size) < 80:           # keyed away almost everything -> unusable
            return None
        return im
    except Exception as e:  # noqa: BLE001
        print(f"[scene] chroma key failed: {e}", flush=True)
        return None


def illustration_subjects(labels, context: str = "") -> dict:
    """Turn terse data labels ('Venue', 'Band/DJ') into concrete visual subjects
    ('a grand wedding venue building') via the LLM, so each cut-out illustrates
    the right thing. Falls back to 'label + context' if the LLM is unavailable."""
    labels = list(labels)
    out = {l: f"{l} {context}".strip() for l in labels}
    try:
        import json
        from script_generator import _call_llm, _strip_fence
        sysp = ("You turn data labels into concrete, literal single-subject "
                "visual descriptions for standalone illustrations. JSON only.")
        user = (f"Context: {context}. For each label give a vivid, concrete "
                "4-7 word description of ONE object or simple scene that best "
                "represents it as an isolated illustration (no text, no people "
                "unless essential). Labels: " + json.dumps(labels)
                + ". Return a JSON object mapping each EXACT label to its phrase.")
        data = json.loads(_strip_fence(_call_llm(sysp, user)))
        for l in labels:
            if isinstance(data.get(l), str) and data[l].strip():
                out[l] = data[l].strip()
    except Exception as e:  # noqa: BLE001
        print(f"[scene] subject LLM skipped: {e}", flush=True)
    return out


def _ensure_rembg_model():
    """rembg auto-downloads u2net.onnx from a GitHub release, which the agent
    proxy blocks (HTTPError) — so cut-outs silently fell back to the rough
    chroma key. Pre-fetch the model from a mirror via curl (which works through
    the proxy) so rembg gets crisp ML background removal everywhere."""
    import os, subprocess
    home = os.path.expanduser("~/.u2net")
    dest = os.path.join(home, "u2net.onnx")
    if os.path.exists(dest) and os.path.getsize(dest) > 1_000_000:
        return
    os.makedirs(home, exist_ok=True)
    for url in (
        "https://huggingface.co/tomjackson2023/rembg/resolve/main/u2net.onnx",
        "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx",
    ):
        try:
            subprocess.run(["curl", "-sSL", "-m", "180", "-o", dest, url],
                           check=True)
            if os.path.getsize(dest) > 1_000_000:
                print(f"[scene] rembg model ready ({url.split('/')[2]})", flush=True)
                return
        except Exception:  # noqa: BLE001
            continue


def _remove_bg(img):
    """Isolate the subject. Prefer rembg (ML, works on any background); fall
    back to the chroma-green key when rembg isn't installed."""
    try:
        _ensure_rembg_model()
        from rembg import remove
        from PIL import Image
        r = remove(img)
        if isinstance(r, Image.Image):
            r = r.convert("RGBA")
            bbox = r.getbbox()
            if bbox:
                r = r.crop(bbox)
            if min(r.size) >= 80:
                return r
    except Exception as e:  # noqa: BLE001
        print(f"[scene] rembg unavailable ({type(e).__name__}); chroma fallback",
              flush=True)
    return _chroma_cut(img)


def subject_cutout(subject: str, slug: str, tag: str,
                   *, cache_dir: Path = CUTOUT_DIR) -> Path | None:
    """A transparent illustration of `subject` (Pollinations on chroma green,
    keyed out, cropped). Cached. None on any failure -> caller skips it."""
    import hashlib
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in f"{slug}__{tag}")
    dest = cache_dir / f"{safe}.png"
    if dest.exists() and dest.stat().st_size > 2048:
        return dest
    if not (subject or "").strip():
        return None
    prompt = (f"{subject}, single subject, centered, isolated on a solid pure "
              "chroma key green background, bold flat vector illustration, "
              "vibrant, clean, no text, no border")
    seed = int(hashlib.sha1(prompt.encode()).hexdigest()[:8], 16)
    img = _pollinations_raw(prompt, seed, size=576)   # smaller -> faster rembg
    if img is None:
        return None
    cut = _remove_bg(img)
    if cut is None:
        return None
    cut.save(dest)
    print(f"[scene] cutout OK -> {dest.name}", flush=True)
    return dest


PHOTO_DIR = REPO / "state" / "subject_photos"

# Wikimedia is full of non-photographic files (logos, flags, maps, diagrams,
# charts, coats of arms, icons). For "show me what it looks like" we want an
# actual PHOTO, so reject these by filename/extension.
_BAD_PHOTO = re.compile(
    r"(\.svg|logo|icon|map|diagram|chart|graph|flag|seal|"
    r"coat[_-]?of[_-]?arms|emblem|symbol|schematic|blueprint|"
    r"wordmark|banner|\.gif)", re.I)


def _is_photo_url(url: str) -> bool:
    return not _BAD_PHOTO.search(url or "")


_STOP = {"the", "and", "for", "with", "from", "into", "are", "was", "you",
         "his", "her", "its", "over", "than", "how", "what", "why", "top",
         "most", "best", "fastest", "biggest", "largest", "world", "worlds"}


def _tok(s: str) -> set:
    """Content tokens of a phrase (lowercased alnum words >2 chars, no stops)."""
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower())
            if len(w) > 2 and w not in _STOP}


def _photo_relevance(url: str, subj_tokens: set) -> int:
    """How well a candidate URL's filename matches the subject. Used to PICK the
    best on-topic photo instead of blindly taking the first that loads."""
    import urllib.parse
    name = urllib.parse.unquote(url.rsplit("/", 1)[-1]) if url else ""
    return len(_tok(name) & subj_tokens)


def subject_photo(subject: str, slug: str, tag: str, *, context: str = "",
                  cache_dir: Path = PHOTO_DIR) -> Path | None:
    """A REAL photo of `subject` pulled off the internet (Wikipedia / Wikimedia
    Commons via topic_media), downloaded + cached. This is what viewers want —
    an actual picture of the thing being discussed, not an illustration. Returns
    a local image Path, or None if nothing relevant was found."""
    import os
    import shutil
    # Channel doctrine: a wrong photo is worse than none. Filename-token
    # relevance is too noisy to reliably tell an on-topic photo from an off-
    # topic one (it put a CAR behind an egg-price stat), so auto-fetched photos
    # are OFF by default. Re-enable with SCENE_PHOTOS=on — the relevance gate
    # below still filters — or (later) behind a vision relevance check.
    if os.environ.get("SCENE_PHOTOS", "off").lower() in ("off", "0", "false"):
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in f"{slug}__{tag}")
    dest = cache_dir / f"{safe}.jpg"
    if dest.exists() and dest.stat().st_size > 2048:
        return dest
    if not (subject or "").strip():
        return None
    try:
        import topic_media
        import entity_media
    except Exception:  # noqa: BLE001
        return None
    # Try the full phrase first, then progressively simpler queries.
    queries, seen = [], set()
    for q in (subject, context, " ".join(subject.split()[:3])):
        q = (q or "").strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            queries.append(q)
    # Gather every candidate URL (best-first per source), then RANK by how well
    # each filename matches the subject so we return the most on-topic photo, not
    # just the first that happens to load. Position is the tiebreaker, so the
    # trusted Wikipedia lead still wins when nothing scores higher.
    cands, seen_u = [], set()
    for q in queries:
        try:
            urls = topic_media.search(q, context) or []
        except Exception:  # noqa: BLE001
            continue
        for url in urls[:6]:
            if url in seen_u or not _is_photo_url(url):
                continue
            seen_u.add(url)
            cands.append(url)
    subj_tokens = _tok(subject)
    # RELEVANCE GATE: a filename-token overlap of 1-2 is noise (it's how a photo
    # of a CAR ended up behind an 'egg prices' stat). Require the photo to
    # actually contain the PRIMARY subject word (the longest, most specific
    # content token) AND clear a score floor. If nothing qualifies, return None
    # and let the scene use its designed look — no junk image.
    import urllib.parse
    min_score = int(os.environ.get("SCENE_PHOTO_MIN_SCORE", "2"))
    primary = max(subj_tokens, key=len) if subj_tokens else None

    def _name_tokens(u: str) -> set:
        return _tok(urllib.parse.unquote((u or "").rsplit("/", 1)[-1]))

    ranked = sorted(range(len(cands)),
                    key=lambda i: (-_photo_relevance(cands[i], subj_tokens), i))
    for i in ranked:
        url = cands[i]
        ntok = _name_tokens(url)
        score = len(ntok & subj_tokens)
        # strong = contains the primary subject word, or clears the score floor
        strong = (primary in ntok) or (score >= min_score)
        if not strong:
            continue
        try:
            if not entity_media.url_is_image(url):
                continue
            p = hook_media._download(url, cache_dir)
            if p and Path(p).stat().st_size > 2048:
                if Path(p) != dest:
                    shutil.copyfile(p, dest)
                print(f"[scene] subject photo OK (score {score}, "
                      f"'{primary}' matched) -> {dest.name}", flush=True)
                return dest
        except Exception:  # noqa: BLE001
            continue
    print(f"[scene] no on-topic photo for '{subject}' "
          f"(primary='{primary}') — using designed look, no junk image",
          flush=True)
    return None


def subject_photo_cutout(subject: str, slug: str, tag: str, *, context: str = "",
                         cache_dir: Path = CUTOUT_DIR) -> Path | None:
    """A REAL photo of `subject` with its background removed -> a transparent
    cut-out. This is the fallback for `subject_cutout` when the AI illustrator is
    down: we still get a photo of the actual thing, but keyed out so it blends
    into a scene (a race lane, a road) instead of reading as a clunky box.
    Cached under the cut-out dir. None on any failure -> caller skips it."""
    from PIL import Image
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in f"{slug}__{tag}")
    dest = cache_dir / f"{safe}.png"
    if dest.exists() and dest.stat().st_size > 2048:
        return dest
    pth = subject_photo(subject, slug, f"{tag}-src", context=context)
    if not pth:
        return None
    try:
        img = Image.open(pth).convert("RGBA")
    except Exception:  # noqa: BLE001
        return None
    cut = _remove_bg(img)
    if cut is None or min(cut.size) < 40:
        return None
    # Only accept a genuine cut-out: if almost nothing was keyed away the result
    # is really a rectangular photo (chroma-key fallback on a non-green image), so
    # reject it rather than render a "box" in the race.
    try:
        alpha = cut.split()[3]
        hist = alpha.histogram()
        transparent = sum(hist[:32])
        if transparent < 0.08 * (cut.width * cut.height):
            return None
    except Exception:  # noqa: BLE001
        return None
    cut.save(dest)
    print(f"[scene] photo cut-out OK -> {dest.name}", flush=True)
    return dest


def fetch_hook_image(story, *, cache_dir: Path = CACHE_DIR) -> Path | None:
    """A REAL full-bleed photo of the story's subject for the hook — a genuine
    picture of the thing (Wikipedia/Commons), NEVER an AI still. Falls back to
    None (designed background) if no relevant photo is found. No AI generation:
    the AI mood-image was generic and tanked the first-second retention."""
    if getattr(story, "hook_image", None) is False:
        return None
    cands = hook_media._candidates(story)
    subject = (getattr(story, "hook_query", "") or " ".join(cands[:2])
               or getattr(story, "title", "")).strip()
    return subject_photo(subject, getattr(story, "slug", "story"), "hookbg",
                         context=getattr(story, "hook", "") or "")
