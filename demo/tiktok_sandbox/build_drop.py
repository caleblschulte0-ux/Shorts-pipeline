"""Assemble the Netlify drag-and-drop folder for the Shorts Media Sandbox demo.

Every original file of the live site comes byte-for-byte from the package
that is on the site now (the FINAL-WITH-CALLBACK zip), and is re-hashed
after copying; only new paths are added:

    app-assets/          the demo's stylesheet, posters, the short to post
    netlify.toml         two shadowing rules (the app, the callback)
    netlify/functions/   one function, with config.json inlined

config.json (sandbox client key, secret, redirect URI, a cookie secret) is
read from beside this script and never copied anywhere else.

    python demo/tiktok_sandbox/build_drop.py
"""
from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ZIP = Path.home() / "Downloads" / "Shorts-Media-TikTok-Review-FINAL-WITH-CALLBACK.zip"
OUT = Path.home() / "Downloads" / "Shorts-Media-Sandbox-Drop"
MOCKUP = HERE.parent / "tiktok_review" / "netlify_app"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    config_path = HERE / "config.json"
    if not config_path.is_file():
        print(f"missing {config_path}: copy config.example.json and fill the sandbox key and secret", file=sys.stderr)
        return 1
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for key in ("client_key", "client_secret", "redirect_uri"):
        if not str(config.get(key) or "").strip():
            print(f"config.json: {key} is empty", file=sys.stderr)
            return 1
    config.setdefault("cookie_secret", secrets.token_urlsafe(32))
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # 1. The originals, byte-identical, and proven so.
    expected = {}
    with zipfile.ZipFile(ZIP) as z:
        for info in z.infolist():
            if info.is_dir() or info.filename == "DEPLOY-THIS-FINAL-PACKAGE.txt":
                continue
            data = z.read(info.filename)
            target = OUT / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            expected[info.filename] = hashlib.sha256(data).hexdigest()
    for rel, digest in expected.items():
        assert sha(OUT / rel) == digest, rel
    print(f"originals: {len(expected)} files copied and re-hashed identical")

    # 2. The demo's own assets, under a path no original uses.
    assets = OUT / "app-assets"
    (assets / "media").mkdir(parents=True)
    (assets / "img").mkdir(parents=True)
    shutil.copy2(HERE / "app.css", assets / "app.css")
    for f in (HERE / "media").iterdir():
        shutil.copy2(f, assets / "media" / f.name)
    for f in (MOCKUP / "img").iterdir():
        shutil.copy2(f, assets / "img" / f.name)
    shutil.copy2(MOCKUP / "img" / "avatar-caleb-sandbox.svg", assets / "img" / "avatar.svg")
    shutil.copy2(HERE / "netlify.toml", OUT / "netlify.toml")

    # 3. The function, config inlined.
    fn_dir = OUT / "netlify" / "functions"
    fn_dir.mkdir(parents=True)
    source = (HERE / "functions" / "app.js").read_text(encoding="utf-8")
    assert source.count("__CONFIG__") == 1
    public = {k: config[k] for k in ("client_key", "client_secret", "redirect_uri", "cookie_secret")}
    (fn_dir / "app.js").write_text(source.replace("__CONFIG__", json.dumps(public)), encoding="utf-8")

    added = sorted(str(p.relative_to(OUT)) for p in OUT.rglob("*") if p.is_file() and str(p.relative_to(OUT)).replace("\\", "/") not in expected)
    print(f"added: {len(added)} files -> {OUT}")
    for rel in added:
        print("  +", rel)
    print("Drag the folder onto the site's Deploys page (Netlify replaces the whole site with it).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
