"""judging_store — durable, append-only judging evidence, shared by every channel.

THE LAW THIS MODULE ENFORCES:

    A judge response that cannot be viewed after the runner disappears is
    treated as MISSING judge evidence.

Judge output used to live in Actions console logs, which evaporate with the
runner, so a green workflow could hide every complaint that mattered. Every
judge response — raw and normalized, success, failure and abstention — is
written under the render package:

    <out>_pkg/judging/
      attempt_01/
        manifest.json          identity: mp4 sha256, package manifest hash,
                               timestamps, rubric version, policy snapshot
        <judge>_raw.json       exactly what the judge returned, untouched
        <judge>_normalized.json the schema the repair engine consumes
        combined_verdict.json  merged view + the binding policy decision
        repair_plan.json       the ranked plan produced from those findings
        comparison.json        movement vs the previous attempt
      attempt_02/ ...
      final_summary.json

Attempt directories are NEVER overwritten: ``next_attempt()`` always returns
one past the highest that exists, so a resumed or re-driven run appends to the
history instead of erasing it.

Every response is bound to the exact artifact it judged (mp4 sha256 + package
manifest hash). A changed video therefore invalidates old evidence by
construction — ``evidence_for()`` will not return a response whose binding does
not match the current file.

No media is ever written here; these are small JSON files, safe to upload as a
workflow artifact and safe (unlike renders) to keep.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
_SAFE = re.compile(r"[^a-z0-9_.-]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slugify(name: str) -> str:
    return _SAFE.sub("_", str(name).strip().lower()) or "judge"


def pkg_dir(out: Path) -> Path:
    return Path(out).with_name(Path(out).stem + "_pkg")


def _sha256(p: Path) -> str | None:
    try:
        import sys
        if str(Path(__file__).resolve().parent.parent / "scripts") not in sys.path:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import artifact_identity
        return artifact_identity.sha256_file(Path(p))
    except Exception:  # noqa: BLE001 — identity is best-effort, absence is recorded
        return None


class JudgingStore:
    """Append-only judging history for one render output."""

    def __init__(self, out: Path):
        self.out = Path(out)
        self.root = pkg_dir(self.out) / "judging"

    # ------------------------------------------------------------------ paths
    def attempt_dir(self, attempt: int) -> Path:
        return self.root / f"attempt_{int(attempt):02d}"

    def existing_attempts(self) -> list[int]:
        if not self.root.exists():
            return []
        ns = []
        for p in self.root.glob("attempt_*"):
            try:
                ns.append(int(p.name.split("_", 1)[1]))
            except (IndexError, ValueError):
                continue
        return sorted(ns)

    def next_attempt(self) -> int:
        """One past the highest attempt on disk. Never returns a number whose
        directory already exists, so prior evidence cannot be overwritten."""
        ns = self.existing_attempts()
        return (ns[-1] + 1) if ns else 1

    # ------------------------------------------------------------------ write
    def open_attempt(self, attempt: int | None = None, *,
                     policy: dict | None = None,
                     escalation: str = "local",
                     story_path: Path | None = None) -> int:
        """Create the attempt directory and stamp its identity manifest.
        Refuses to reuse an attempt number that already exists."""
        n = self.next_attempt() if attempt is None else int(attempt)
        d = self.attempt_dir(n)
        if d.exists():
            raise FileExistsError(
                f"attempt {n} already recorded at {d} — judging evidence is "
                "append-only; call next_attempt()")
        d.mkdir(parents=True)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "attempt": n,
            "created_at": _now(),
            "out": str(self.out),
            "mp4_sha256": _sha256(self.out) if self.out.exists() else None,
            "package_manifest_sha256": self._pkg_manifest_hash(),
            "story_path": str(story_path) if story_path else None,
            "escalation": escalation,
            "policy": policy or {},
            "runner": {
                "github_run_id": os.environ.get("GITHUB_RUN_ID"),
                "github_sha": os.environ.get("GITHUB_SHA"),
                "github_ref": os.environ.get("GITHUB_REF_NAME"),
            },
        }
        (d / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return n

    def _pkg_manifest_hash(self) -> str | None:
        m = pkg_dir(self.out) / "manifest.json"
        if not m.exists():
            return None
        try:
            return json.loads(m.read_text()).get("manifest_sha256")
        except Exception:  # noqa: BLE001
            return None

    def record(self, attempt: int, judge: str, *, raw, normalized: dict | None = None,
               status: str = "ok", error: str = "", model: str = "",
               provider: str = "", rubric_version: str = "",
               confidence: float | None = None) -> dict:
        """Persist one judge's response. `raw` is written verbatim (as JSON when
        it is JSON-able, otherwise as a string field) so nothing the judge said
        is lost to normalization. Failures and abstentions are RECORDED, never
        silently omitted — a judge that could not run is evidence too."""
        d = self.attempt_dir(attempt)
        d.mkdir(parents=True, exist_ok=True)
        key = _slugify(judge)
        raw_doc = {
            "judge": judge, "status": status, "recorded_at": _now(),
            "model": model, "provider": provider,
            "rubric_version": rubric_version,
            "error": str(error)[:2000],
            "mp4_sha256": _sha256(self.out) if self.out.exists() else None,
            "package_manifest_sha256": self._pkg_manifest_hash(),
        }
        try:
            json.dumps(raw)
            raw_doc["response"] = raw
        except (TypeError, ValueError):
            raw_doc["response_text"] = str(raw)
        (d / f"{key}_raw.json").write_text(json.dumps(raw_doc, indent=2) + "\n")

        norm = dict(normalized or {})
        norm.update({
            "judge": judge, "status": status,
            "model": model, "provider": provider,
            "rubric_version": rubric_version,
            "recorded_at": raw_doc["recorded_at"],
            "mp4_sha256": raw_doc["mp4_sha256"],
            "package_manifest_sha256": raw_doc["package_manifest_sha256"],
        })
        if confidence is not None:
            norm["confidence"] = float(confidence)
        if status in ("failed", "abstained"):
            norm.setdefault("pass", None)
            norm["error"] = str(error)[:500]
        (d / f"{key}_normalized.json").write_text(json.dumps(norm, indent=2) + "\n")
        return norm

    def write(self, attempt: int, name: str, doc) -> Path:
        d = self.attempt_dir(attempt)
        d.mkdir(parents=True, exist_ok=True)
        p = d / (name if name.endswith(".json") else f"{name}.json")
        p.write_text(json.dumps(doc, indent=2, default=str) + "\n")
        return p

    def write_final_summary(self, doc) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        p = self.root / "final_summary.json"
        p.write_text(json.dumps(doc, indent=2, default=str) + "\n")
        return p

    # ------------------------------------------------------------------- read
    def read(self, attempt: int, name: str):
        p = self.attempt_dir(attempt) / (
            name if name.endswith(".json") else f"{name}.json")
        try:
            return json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def normalized(self, attempt: int) -> dict:
        """{judge_name: normalized} for one attempt, including failures."""
        out = {}
        for p in sorted(self.attempt_dir(attempt).glob("*_normalized.json")):
            try:
                d = json.loads(p.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            out[d.get("judge") or p.stem[:-len("_normalized")]] = d
        return out

    def history(self) -> list[dict]:
        """Every attempt's combined verdict, oldest first — the movement record."""
        hist = []
        for n in self.existing_attempts():
            hist.append({
                "attempt": n,
                "manifest": self.read(n, "manifest"),
                "combined": self.read(n, "combined_verdict"),
                "repair_plan": self.read(n, "repair_plan"),
                "comparison": self.read(n, "comparison"),
            })
        return hist

    def evidence_for(self, attempt: int, judge: str) -> dict | None:
        """A judge's normalized response ONLY IF it is bound to the artifact
        currently on disk. A re-render changes the mp4 hash, which invalidates
        every earlier response by construction rather than by convention."""
        d = self.normalized(attempt).get(judge)
        if not d:
            return None
        cur = _sha256(self.out) if self.out.exists() else None
        if d.get("mp4_sha256") and cur and d["mp4_sha256"] != cur:
            return None
        return d


if __name__ == "__main__":
    import sys
    s = JudgingStore(Path(sys.argv[1]))
    print(json.dumps({"attempts": s.existing_attempts(),
                      "next": s.next_attempt()}, indent=2))
