"""exchange_media — the GENERATED-media provider, shared by every channel.

The exchange mailbox (exchange/, scripts/exchange.py) lets another agent
answer asks with assets in Google Drive. This module makes those answers a
first-class MEDIA SOURCE with the same never-raise manners as the rest of
the gateway, and closes the loop the search providers cannot:

  render 1: the gateway comes up totally dry for a query
            -> maybe_request() files exchange/requests/image-auto-<h>.json
               (the id is a HASH OF THE BRIEF, so re-renders converge on one
               ask instead of spamming duplicates)
  offline:  the other agent answers it into Drive + exchange/responses/
  render 2: maybe_fetch(auto_id(query)) finds the answer, downloads it into
            cache/, and the beat gets a real image instead of a text card.

A beat may also PIN a generated asset explicitly: ``"image": {"asset":
"image-20260729-taxes-01", ...}`` — an authored answer always outranks a
search. Asset ids are opaque; nothing selects behavior by story identity.

PROVENANCE (docs/MEDIA_ACQUISITION.md): every asset served here is stamped
source_class "generated", license "AI-generated (exchange)", and the request
brief rides along as the attribution trail — it enters the audit sidecar and
credits like any other source. Generated media depicts ILLUSTRATION, never
EVIDENCE: do not pin it on beats whose point is that a thing really happened.

Contract: ``maybe_*`` returns a result or None, never raises. Files under
cache/ only; the only repo state written is exchange/requests/*.json (small,
committed paperwork by design).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

BOX = REPO / "exchange"
REQ, RES = BOX / "requests", BOX / "responses"
CACHE = REPO / "cache" / "exchange"


def auto_id(brief: str, kind: str = "image") -> str:
    """Deterministic id for an AUTO-FILED ask: the same brief always maps to
    the same id, so a re-render reuses (or finds answered) the same request."""
    h = hashlib.sha1(f"{kind}:{' '.join(str(brief).lower().split())}"
                     .encode()).hexdigest()[:10]
    return f"{kind}-auto-{h}"


def _read(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def maybe_fetch(asset_id: str, kind: str = "image"):
    """The answered asset as a gateway candidate dict (with a local 'path'),
    or None: no response yet, bad pointer, not shared, or any download
    trouble. Cached downloads are reused."""
    try:
        import exchange as ex
        res = _read(RES / f"{asset_id}.json")
        if res is None:
            return None
        fid = res.get("drive_file_id") or ex.drive_file_id(
            res.get("drive_url", ""))
        if not fid:
            return None
        req = _read(REQ / f"{asset_id}.json") or {}
        suffix = Path(res.get("filename") or "asset.png").suffix or ".png"
        dest = CACHE / f"{asset_id}{suffix}"
        if not (dest.exists() and dest.stat().st_size > 4096):
            class _A:  # exchange.cmd_fetch's argument shape
                id = asset_id
                out = str(dest)
                big = kind != "image"
            if ex.cmd_fetch(_A()) != 0:
                return None
        if not (dest.exists() and dest.stat().st_size > 4096):
            return None
        return {
            "path": str(dest),
            "source": "exchange",
            "source_class": "generated",
            "kind": kind,
            "license": "AI-generated (exchange)",
            "attribution": ("Generated asset via exchange "
                            f"({res.get('by', 'agent')}); brief: "
                            f"{str(req.get('brief', ''))[:140]}"),
            "title": res.get("filename") or asset_id,
        }
    except Exception:  # noqa: BLE001 — a media source never crashes a render
        return None


def gateway_was_operational(kind: str = "image") -> bool:
    """True when at least one provider that can serve `kind` was actually
    usable (key present, circuit closed).

    This distinguishes the two very different reasons a search comes up dry:
      - CONTENT gap: providers ran and nobody has that picture -> a generated
        asset is the right answer, file the ask.
      - ENVIRONMENT gap: no provider could even be called (missing API keys,
        every circuit open) -> the miss says nothing about the content, and
        filing an ask would send the other agent to draw something the real
        runner fills with real photography. Stay quiet.
    Without this, every keyless local/diagnostic render spams false media
    debts (observed 2026-07-30: a local render filed an ask for "person
    walking outdoors sunset", which the CC pools serve easily).
    """
    try:
        from data_learning.provider_routing import records
        return any(r.healthy and kind in r.capabilities for r in records())
    except Exception:  # noqa: BLE001 — unknown health: assume operational so a
        return True    # real content gap is never silently swallowed


def maybe_request(brief: str, purpose: str = "", kind: str = "image",
                  aspect: str = "16:9",
                  style: str = "photographic, documentary, no text in frame, "
                               "no watermarks, no recognisable faces") -> str | None:
    """File an auto-ask for the other agent (id derived from the brief).
    Returns the id, whether the request was just written or already existed;
    None when the file could not be written OR when the gateway was not
    actually operational (see gateway_was_operational). Never raises."""
    try:
        if not gateway_was_operational(kind):
            print(f"[exchange] NOT filing an ask for {str(brief)[:50]!r}: no "
                  f"{kind} provider was reachable, so this miss is about "
                  "credentials, not content")
            return None
        rid = auto_id(brief, kind)
        p = REQ / f"{rid}.json"
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({
                "id": rid,
                "created_at": datetime.now(timezone.utc)
                .isoformat(timespec="seconds"),
                "from": "pipeline-auto",
                "to": "chatgpt",
                "kind": kind,
                "brief": str(brief),
                "purpose": str(purpose)[:300],
                "constraints": {"aspect": aspect, "style": style},
            }, indent=2) + "\n")
            print(f"[exchange] filed auto-request {rid}: {str(brief)[:70]!r}")
        return rid
    except Exception:  # noqa: BLE001
        return None


def open_requests() -> list[dict]:
    """Unanswered asks — the pipeline's outstanding media debts."""
    out = []
    try:
        for p in sorted(REQ.glob("*.json")):
            d = _read(p)
            if d is None or (RES / p.name).exists():
                continue
            out.append({"id": d.get("id", p.stem),
                        "kind": d.get("kind", "?"),
                        "brief": str(d.get("brief", ""))[:90],
                        "from": d.get("from", "?")})
    except Exception:  # noqa: BLE001
        pass
    return out


if __name__ == "__main__":
    reqs = open_requests()
    print(f"{len(reqs)} open exchange request(s)")
    for r in reqs:
        print(f"  {r['id']}  [{r['kind']}]  {r['brief']}")
