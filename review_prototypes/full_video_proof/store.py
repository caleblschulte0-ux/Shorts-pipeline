from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
import os

from .models import SuiteRunProof


class ProofStoreError(RuntimeError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


class ProofStore:
    """Append-only proof storage; a run ID can never be overwritten."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, proof: SuiteRunProof) -> Path:
        proof.validate()
        destination = self.root / proof.run_id
        if destination.exists():
            raise ProofStoreError(f"run already exists: {proof.run_id}")
        staging = Path(tempfile.mkdtemp(prefix=f".{proof.run_id}-", dir=self.root))
        try:
            payload = asdict(proof)
            data = _canonical_bytes(payload)
            (staging / "proof.json").write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            (staging / "proof.sha256").write_text(digest + "\n", encoding="utf-8")
            os.replace(staging, destination)
        except Exception:
            import shutil
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return destination

    def verify(self, run_id: str) -> bool:
        path = self.root / run_id
        data = (path / "proof.json").read_bytes()
        expected = (path / "proof.sha256").read_text(encoding="utf-8").strip()
        return hashlib.sha256(data).hexdigest() == expected
