"""Fetch CC0 assets (Poly Haven models, HDRI skies, textures) for 3D shorts, run in CI (2026-11-24).

Hand-modelled props read as toys to every judge (lava board rounds 1-3: box boats, cube houses, clay smoke). Poly Haven
is CC0 and real-world scanned, but this workspace's proxy refuses it; GitHub's runners reach it. So
.github/workflows/data3d_assets.yml runs this on a push of .github/triggers/data3d_assets and commits what it fetched to
the orphan branch `data3d-assets` (never main: binaries stay out of the code history), where a session fetches it with
plain git.

Trigger lines:  index            write polyhaven/index.json (every asset: name, type, categories, tags)
                model <id> [res] a model as glTF (default 1k) with its textures
                hdri <id> [res]  an HDRI sky as .hdr (default 2k)
                texture <id> [res]  a PBR texture set as glTF-ready maps (default 1k)
                env <id>         a whole real PLACE (a full-environment HDRI, not a pure sky): the 2k .hdr that lights the
                                 scene and the 8k tonemapped JPG the lens sees behind it (store/director.py)
A file already on the branch is not fetched again, so the trigger can keep every line it ever had.
"""
import json, os, sys, urllib.request
from pathlib import Path

API = "https://api.polyhaven.com"
BIG = 60 << 20         # a model heavier than this is left out: the branch has to push, and a session has to unpack it
UA = {"User-Agent": "shorts-pipeline-data3d-assets"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def save(url, path):
    if path.exists() and path.stat().st_size > 0:
        return                      # already on the branch
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(get(url))
    print(f"  {path} {path.stat().st_size // 1024} KB")


def index(out):
    assets = json.loads(get(f"{API}/assets"))
    slim = {k: {"name": v.get("name"), "type": {0: "hdri", 1: "texture", 2: "model"}.get(v.get("type")),
                "categories": v.get("categories"), "tags": v.get("tags")} for k, v in assets.items()}
    p = out / "polyhaven" / "index.json"; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(slim, indent=0, sort_keys=True)); print(f"index: {len(slim)} assets")


def gltf(out, aid, res, key="gltf"):
    files = json.loads(get(f"{API}/files/{aid}"))
    sets = files.get(key) or {}
    r = res if res in sets else sorted(sets, key=lambda s: int(s.rstrip("k")))[0]
    f = sets[r]["gltf"]
    base = out / "polyhaven" / aid
    save(f["url"], base / Path(f["url"]).name)
    for rel, inc in (f.get("include") or {}).items():
        save(inc["url"], base / rel)


def hdri(out, aid, res):
    files = json.loads(get(f"{API}/files/{aid}"))["hdri"]
    r = res if res in files else "2k"
    save(files[r]["hdr"]["url"], out / "polyhaven" / "hdri" / f"{aid}_{r}.hdr")


def env(out, aid):
    files = json.loads(get(f"{API}/files/{aid}"))
    hd = files["hdri"]
    save(hd["2k" if "2k" in hd else sorted(hd, key=lambda s: int(s.rstrip("k")))[0]]["hdr"]["url"], out / "polyhaven" / "hdri" / f"{aid}_2k.hdr")
    tm = (files.get("tonemapped") or {}).get("url")
    if tm:
        save(tm, out / "polyhaven" / "env" / f"{aid}.jpg")
    elif "4k" in hd:                # no tonemapped plate: the 4k .hdr is what the lens sees
        save(hd["4k"]["hdr"]["url"], out / "polyhaven" / "hdri" / f"{aid}_4k.hdr")


def main(trigger, out):
    out = Path(out); ok = bad = 0
    for line in Path(trigger).read_text().splitlines():
        w = line.split("#")[0].split()
        if not w:
            continue
        try:
            if w[0] == "index":
                index(out)
            elif w[0] == "model":
                gltf(out, w[1], w[2] if len(w) > 2 else "1k")
            elif w[0] == "texture":
                gltf(out, w[1], w[2] if len(w) > 2 else "1k")
            elif w[0] == "hdri":
                hdri(out, w[1], w[2] if len(w) > 2 else "2k")
            elif w[0] == "env":
                env(out, w[1])
            else:
                print(f"skip: {line}"); continue
            ok += 1
        except Exception as e:  # one bad id never costs the rest
            bad += 1; print(f"FAILED {line}: {e}")
    for d in sorted((out / "polyhaven").iterdir()):     # GitHub refuses a file over 100 MB, and ONE refused file refuses the
        big = [f for f in d.rglob("*") if f.is_file() and f.stat().st_size > BIG] if d.is_dir() else []   # whole push (2026-11-28:
        if big:                                         # a 199 MB tree cost every asset of that run, with the job green)
            import shutil
            print(f"TOO BIG, dropped {d.name}: {big[0].name} is {big[0].stat().st_size >> 20} MB (limit {BIG >> 20})"); shutil.rmtree(d)
    print(f"fetched {ok}, failed {bad}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
