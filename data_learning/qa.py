"""Pre-publish QA for generated packages.

These checks enforce the two hard contracts of the base renderer (verbatim
phrases) plus the editorial guardrails from the prompt spec (sourced
numbers, honest metadata, caption density). :func:`validate` returns a list
of failure strings — empty means the package is safe to ship.
"""
from __future__ import annotations

import re


def _is_substring(phrase: str, script: str) -> bool:
    return phrase.lower() in script.lower()


def validate(pkg: dict, *, source_allowlist: list[str] | None = None) -> list[str]:
    errors: list[str] = []
    script = pkg.get("script", "")

    if not script.strip():
        errors.append("empty script")

    # 1. Every shot/punch phrase must be a verbatim substring of the script.
    for s in pkg.get("shots", []):
        ph = s.get("phrase", "")
        if not ph or not _is_substring(ph, script):
            errors.append(f"shot phrase not in script: {ph!r}")
    for p in pkg.get("punches", []):
        ph = p.get("phrase", "")
        if not ph or not _is_substring(ph, script):
            errors.append(f"punch phrase not in script: {ph!r}")

    # 2. Structural sanity.
    if not pkg.get("shots"):
        errors.append("no shots")
    if not pkg.get("title"):
        errors.append("missing title")
    if len(pkg.get("title", "")) > 100:
        errors.append("title exceeds 100 chars (YouTube limit)")

    # 3. Script length — the channel format is ~50-90 words.
    words = len(script.split())
    if words and not (25 <= words <= 110):
        errors.append(f"script word count {words} outside 25-110")

    # 4. Provenance: numbers should trace to facts, and a source footer
    #    must exist so the video can cite on-screen.
    dl = pkg.get("_data_learning", {})
    if not dl.get("source_footer"):
        errors.append("missing source footer (no on-screen citation)")
    if not dl.get("facts"):
        errors.append("no traceable facts attached")

    # 5. Every number spoken in the script should appear in the fact table
    #    (catches a stray/hallucinated figure). Include the 1-decimal
    #    rounded form of each fact value, since narration rounds (e.g. a
    #    0.08 fact is spoken as "0.1 percent").
    fact_values: set[float] = set()
    for f in dl.get("facts", []):
        fv = _norm_num(str(f.get("value")))
        if fv is not None:
            fact_values.add(fv)
            fact_values.add(round(fv, 1))
    for tok in re.findall(r"\d[\d,]*\.?\d*", script):
        n = _norm_num(tok)
        if n is None:
            continue
        # Year-like integers (1900-2100) are period labels, not metrics.
        if "." not in tok and 1900 <= n <= 2100:
            continue
        if not any(_close(n, fv) for fv in fact_values):
            # Only flag things that look like a metric (decimal or large).
            if "." in tok or n >= 1000:
                errors.append(f"script number {tok!r} not in fact table")

    # 6. Source allowlist (if the niche pins approved publishers/domains).
    if source_allowlist:
        footer = dl.get("source_footer", "")
        if not any(a.lower() in footer.lower() for a in source_allowlist):
            errors.append(f"source not in allowlist: {footer!r}")

    # 7. Caption density — punches are short ALL-CAPS stingers, not lines.
    for p in pkg.get("punches", []):
        if len(p.get("text", "").split()) > 4:
            errors.append(f"punch text too long: {p.get('text')!r}")

    return errors


def _norm_num(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        return round(float(str(s).replace(",", "")), 2)
    except (ValueError, TypeError):
        return None


def _close(a: float, b: float, tol: float = 0.06) -> bool:
    if a == b:
        return True
    if b == 0:
        return abs(a) <= tol
    return abs(a - b) / abs(b) <= tol
