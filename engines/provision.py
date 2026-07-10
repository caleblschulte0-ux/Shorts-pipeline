"""Explicit provisioning for engines: pip deps + pinned model downloads.

This is the ONLY place in the package that touches the network, and it only
runs when invoked (`python -m engines install <engine>`, or maybe_* with
ENGINES_AUTO_PROVISION=1). Downloads are verified against the pinned
SHA-256 before being moved into place atomically, so a torn download can
never masquerade as a valid model.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import urllib.request
from pathlib import Path

from engines import MODELS_DIR, REGISTRY

_PIP_DEPS = {
    "parallax": ["opencv-python-headless>=4.8", "onnxruntime>=1.16",
                 "numpy>=1.24"],
    "still_motion": [],
}


def _pip_install(pkgs: list[str]) -> bool:
    if not pkgs:
        return True
    print(f"[provision] pip install {' '.join(pkgs)}")
    rc = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                         *pkgs]).returncode
    return rc == 0


def _download_model(spec: dict) -> bool:
    dest = MODELS_DIR / spec["name"]
    if dest.is_file():
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        if digest == spec["sha256"]:
            print(f"[provision] model already present + verified: {dest}")
            return True
        print(f"[provision] model checksum mismatch — re-downloading")
        dest.unlink()
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(".part")
    print(f"[provision] downloading {spec['url']} "
          f"({spec['size_bytes'] / 1e6:.0f} MB)")
    try:
        with urllib.request.urlopen(spec["url"], timeout=120) as r, \
                open(part, "wb") as f:
            sha = hashlib.sha256()
            while chunk := r.read(1 << 20):
                f.write(chunk)
                sha.update(chunk)
    except Exception as e:  # noqa: BLE001
        print(f"[provision] download failed: {e}")
        part.unlink(missing_ok=True)
        return False
    if sha.hexdigest() != spec["sha256"]:
        print(f"[provision] SHA-256 MISMATCH — refusing to install.\n"
              f"  expected {spec['sha256']}\n  got      {sha.hexdigest()}")
        part.unlink()
        return False
    part.replace(dest)  # atomic: verified bytes or nothing
    print(f"[provision] verified + installed: {dest}")
    return True


def install(name: str) -> bool:
    """Provision one engine. Returns True when `available()` should now pass."""
    meta = REGISTRY.get(name)
    if meta is None or meta.get("kind") != "module":
        print(f"[provision] {name!r} is not an installable engine module "
              f"(external engines are provisioned by the workflows)")
        return False
    ok = _pip_install(_PIP_DEPS.get(name, []))
    if ok and "model" in meta:
        ok = _download_model(meta["model"])
    return ok
