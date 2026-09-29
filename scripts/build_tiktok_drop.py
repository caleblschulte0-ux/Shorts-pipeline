"""Build the Shorts Media Netlify drop: static site + the TikTok function.

The static pages (privacy policy, terms, demo media) are not in git — they
are media and live in the last deployed drop. This takes that drop as the
BASE, drops its old function and netlify.toml, and lays tiktok_app/ over it
with the TikTok app's secrets filled in. Secrets come from a local JSON file
(never commit it: this repo is public) or from the environment.

    python scripts/build_tiktok_drop.py --base old-drop.zip \\
        --config ~/shorts-media-config.json --out Shorts-Media-Drop.zip

config.json keys: client_key, client_secret, cookie_secret
(env: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, SM_COOKIE_SECRET).

The base may be a root-layout drop or one with everything under public/;
the output is always root-layout (the site root is the publish directory).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "tiktok_app"
FUNCTION = APP / "netlify" / "functions" / "app.js"
PLACEHOLDERS = {
    "__TIKTOK_CLIENT_KEY__": ("client_key", "TIKTOK_CLIENT_KEY"),
    "__TIKTOK_CLIENT_SECRET__": ("client_secret", "TIKTOK_CLIENT_SECRET"),
    "__SM_COOKIE_SECRET__": ("cookie_secret", "SM_COOKIE_SECRET"),
}
#: Paths from the base that the build replaces, never carries over.
DROPPED = ("netlify/", "netlify.toml", "package.json")


def fill(source: str, config: dict) -> str:
    for mark, (key, env) in PLACEHOLDERS.items():
        value = str(config.get(key) or os.environ.get(env) or "").strip()
        if not value:
            raise SystemExit(f"missing {key} (config) / {env} (env)")
        if any(c in value for c in "\"\\\n"):
            raise SystemExit(f"{key} contains a quote, backslash or newline")
        source = source.replace(f'"{mark}"', json.dumps(value))
    left = [m for m in PLACEHOLDERS if m in source]
    if left:
        raise SystemExit(f"placeholders left unfilled: {left}")
    return source


def site_files(base: zipfile.ZipFile) -> dict[str, bytes]:
    names = [n for n in base.namelist() if not n.endswith("/")]
    # A public/ layout: the site is whatever sits under public/.
    prefix = "public/" if any(n.startswith("public/") for n in names) else ""
    out = {}
    for n in names:
        if not n.startswith(prefix):
            continue
        rel = n[len(prefix):]
        if rel.startswith(DROPPED) or rel.startswith("__MACOSX/"):
            continue
        out[rel] = base.read(n)
    if "index.html" not in out:
        raise SystemExit("base drop has no index.html at its site root")
    return out


def build(base: Path, config: dict, out: Path) -> Path:
    with zipfile.ZipFile(base) as z:
        files = site_files(z)
    files["netlify.toml"] = (APP / "netlify.toml").read_bytes()
    files["netlify/functions/app.js"] = fill(
        FUNCTION.read_text(encoding="utf-8"), config).encode("utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(files):
            z.writestr(rel, files[rel])
    if shutil.which("node"):
        tmp = out.with_suffix(".check.js")
        tmp.write_bytes(files["netlify/functions/app.js"])
        try:
            subprocess.run(["node", "--check", str(tmp)], check=True)
        finally:
            tmp.unlink()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", type=Path, required=True,
                    help="the last deployed drop (.zip) — supplies the pages")
    ap.add_argument("--config", type=Path,
                    help="local JSON with client_key/client_secret/cookie_secret")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    config = json.loads(a.config.read_text()) if a.config else {}
    print(build(a.base, config, a.out))


if __name__ == "__main__":
    main()
