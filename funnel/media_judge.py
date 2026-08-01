"""Script-aware media judge — is THIS image right for THIS line?

The pre-render gate that decides when to ask ChatGPT for AI media. It does
not ask "is this a nice picture"; it asks "the script says X here, this is
what we would put on screen — does that land?" A shot whose media is generic,
low-res, unverified, over-used, or simply unrelated to its line comes back
`weak`, and weak is a reason to generate something better.

Deterministic and offline: token overlap against the script line, proper-noun
coverage, resolution vs the target frame, source class, and the cross-video
usage ledger. No LLM, no network — so it runs on every shot of every package
for free, every day.

    from funnel import media_judge
    report = media_judge.judge_package(pkg, media_by_shot)
    for v in report["verdicts"]:
        if v["verdict"] != "strong":
            ...  # request AI media using v["ai_prompt"]

Contract matches the funnel: never raises. A judge failure degrades to
`unknown`, which callers treat as "leave it alone", never as "it's fine".
"""
from __future__ import annotations

import re

STOPWORDS = frozenset("""
a an the this that these those and or but if then than so as of in on at to
for with from by about into over after before between out up down off is are
was were be been being do does did doing have has had having i me my we our
you your he him his she her it its they them their what which who whom when
where why how all any both each few more most other some such no nor not only
own same too very can will just should now got get gets getting also new news
video photo image picture footage clip stock
""".split())

# What a channel actually renders into; used for the resolution verdict.
TARGET_MIN_EDGE = 720

# Source classes, best first (see docs/MEDIA_ACQUISITION.md).
CLASS_RANK = {
    "primary_source": 3,
    "open_or_licensed": 2,
    "transformative_evidence": 2,
    "unverified": 1,
}

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9'\-]+")
_PROPER = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*)\b")


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text or "")
            if w.lower() not in STOPWORDS and len(w) > 2}


def _proper_nouns(text: str) -> set[str]:
    """Specific named things in the line — the stuff a generic stock photo
    cannot possibly be showing."""
    out: set[str] = set()
    for m in _PROPER.finditer(text or ""):
        phrase = m.group(1)
        # A sentence-initial capital is not evidence of a proper noun.
        if m.start() == 0 and " " not in phrase:
            continue
        for part in phrase.split():
            if part.lower() not in STOPWORDS:
                out.add(part.lower())
    return out


def _media_text(media: dict) -> str:
    """Everything textual we know about a candidate, for overlap scoring."""
    return " ".join(str(media.get(k) or "") for k in
                    ("title", "description", "query", "alt", "subject",
                     "entity", "provider", "url"))


def judge_shot(shot: dict, media: dict | None, *,
               script: str = "", title: str = "",
               usage_penalty: float = 0.0) -> dict:
    """Score one shot's chosen media against the line it accompanies.

    `media` is whatever the funnel picked: any of url/title/query/width/
    height/source_class/license/provider. None or {} means nothing was found.
    Returns a verdict dict — never raises.
    """
    try:
        phrase = str(shot.get("phrase") or "")
        query = str(shot.get("query") or "")
        reasons: list[str] = []

        if not media or not (media.get("url") or media.get("path")):
            return {
                "verdict": "missing", "score": 0.0,
                "reasons": ["no media found for this line"],
                "phrase": phrase, "query": query,
                "ai_prompt": ai_prompt(shot, script=script, title=title),
                "wants": "image",
            }

        mtext = _media_text(media)
        mtok = _tokens(mtext)
        ptok = _tokens(phrase)
        propers = _proper_nouns(phrase)

        # 1. Does the media relate to the line at all?
        overlap = len(ptok & mtok) / max(1, len(ptok)) if ptok else 0.0

        # 2. Specific things named in the line that the media does not mention.
        #    This is the "doesn't really fit" case: a generic stock photo
        #    standing in for a named subject.
        missing_propers = sorted(propers - mtok) if propers else []

        # 3. Resolution against the render target.
        w = int(media.get("width") or 0)
        h = int(media.get("height") or 0)
        small = bool(w and h and min(w, h) < TARGET_MIN_EDGE)

        # 4. Provenance.
        cls = str(media.get("source_class") or "unverified")
        cls_rank = CLASS_RANK.get(cls, 1)

        score = 0.0
        score += 0.45 * overlap
        score += 0.20 * (0.0 if missing_propers else 1.0)
        score += 0.15 * (0.0 if small else 1.0)
        score += 0.10 * (cls_rank / 3.0)
        score += 0.10                      # baseline for having anything real
        score -= max(0.0, float(usage_penalty))

        if overlap < 0.25:
            reasons.append(f"weak relation to the line "
                           f"({overlap:.0%} term overlap)")
        if missing_propers:
            reasons.append("generic stand-in — line names "
                           + ", ".join(missing_propers[:3])
                           + " but the media does not")
        if small:
            reasons.append(f"low resolution {w}x{h} (target min edge "
                           f"{TARGET_MIN_EDGE})")
        if cls_rank <= 1:
            reasons.append(f"unverified provenance ({cls})")
        if usage_penalty > 0:
            reasons.append(f"reused recently (penalty {usage_penalty:.2f})")

        score = max(0.0, min(1.0, score))
        verdict = "strong" if score >= 0.62 else "weak"
        if verdict == "strong":
            reasons = reasons or ["on-topic, adequate resolution"]

        out = {"verdict": verdict, "score": round(score, 3),
               "reasons": reasons, "phrase": phrase, "query": query,
               "media_url": media.get("url") or media.get("path"),
               "source_class": cls}
        if verdict != "strong":
            out["ai_prompt"] = ai_prompt(shot, script=script, title=title)
            out["wants"] = "image"
        return out
    except Exception:                                    # noqa: BLE001
        return {"verdict": "unknown", "score": 0.0,
                "reasons": ["judge failed"], "phrase": str(shot.get("phrase")
                                                           or "")}


def ai_prompt(shot: dict, *, script: str = "", title: str = "") -> str:
    """The image prompt to hand ChatGPT for a shot we could not fill well.

    Describes the SUBJECT of the line, never the pipeline. (Run 1 of the
    exchange failed by drawing GitHub screenshots — the model had been
    reading a repo. Keeping the prompt strictly about the line's subject is
    the mitigation.)"""
    phrase = str(shot.get("phrase") or "").strip()
    query = str(shot.get("query") or "").strip()
    subject = query or phrase
    bits = [f"An editorial illustration for a short-form video: {subject}."]
    if phrase and phrase.lower() != subject.lower():
        bits.append(f'It accompanies the narration: "{phrase}"')
    bits.append("Photographic realism, dramatic lighting, single clear "
                "subject, centered, no text, no watermarks, no logos, "
                "no user interfaces, no screenshots, no code.")
    return " ".join(bits)


def judge_package(pkg: dict, media_by_shot: dict | list | None = None, *,
                  usage_penalties: dict | None = None) -> dict:
    """Judge every shot in a package.

    `media_by_shot` maps shot index -> media dict (a list works too). A shot
    with no entry is judged `missing`. Returns a report with per-shot verdicts
    and the gap list ready to become exchange requests.
    """
    try:
        shots = pkg.get("shots") or []
        script = pkg.get("script") or ""
        title = pkg.get("title") or ""
        pen = usage_penalties or {}

        def _media_for(i: int, shot: dict):
            if isinstance(media_by_shot, dict):
                return media_by_shot.get(i) or media_by_shot.get(str(i))
            if isinstance(media_by_shot, list) and i < len(media_by_shot):
                return media_by_shot[i]
            # Fall back to whatever the package already pinned.
            if shot.get("image_url"):
                return {"url": shot["image_url"], "query": shot.get("query"),
                        "title": shot.get("phrase")}
            return None

        verdicts = []
        for i, shot in enumerate(shots):
            v = judge_shot(shot, _media_for(i, shot), script=script,
                           title=title,
                           usage_penalty=float(pen.get(i, 0.0) or 0.0))
            v["shot_index"] = i
            verdicts.append(v)

        counts = {"strong": 0, "weak": 0, "missing": 0, "unknown": 0}
        for v in verdicts:
            counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
        gaps = [v for v in verdicts if v["verdict"] in ("weak", "missing")]
        n = max(1, len(verdicts))
        return {
            "slug": pkg.get("slug"),
            "title": title,
            "shot_count": len(verdicts),
            "counts": counts,
            "strong_fraction": round(counts["strong"] / n, 3),
            "verdicts": verdicts,
            "gaps": gaps,
        }
    except Exception:                                    # noqa: BLE001
        return {"slug": pkg.get("slug") if isinstance(pkg, dict) else None,
                "shot_count": 0, "counts": {}, "verdicts": [], "gaps": [],
                "error": "judge_package failed"}
