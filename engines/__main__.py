"""CLI for the engines capability layer.

    python -m engines list
    python -m engines info <engine>
    python -m engines doctor [<engine>]
    python -m engines install <engine>
    python -m engines demo kenburns --image X --out Y [--duration 4]
    python -m engines demo parallax --image X --out Y [--duration 4]

`list`, `info`, and `doctor` are offline and fast — safe for any Claude
session to run as discovery. Only `install` touches the network.
"""
from __future__ import annotations

import argparse
import sys
import time

import engines
from engines import REGISTRY


def _cmd_list(_args) -> int:
    width = max(len(n) for n in REGISTRY)
    print(f"{'ENGINE':<{width}}  {'KIND':<8}  {'STATUS':<12}  AVAILABLE")
    for name, meta in REGISTRY.items():
        try:
            avail = "yes" if engines.available(name) else "no"
        except Exception:
            avail = "no"
        print(f"{name:<{width}}  {meta['kind']:<8}  {meta['status']:<12}  {avail}")
    print("\nFull triage (incl. deferred/rejected tools): docs/ENGINE_REGISTRY.md")
    return 0


def _cmd_info(args) -> int:
    meta = engines.info(args.engine)
    for k, v in meta.items():
        if isinstance(v, dict):
            print(f"{k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        elif isinstance(v, list):
            print(f"{k}:")
            for item in v:
                print(f"    - {item}")
        else:
            print(f"{k}: {v}")
    return 0


def _cmd_doctor(args) -> int:
    targets = [args.engine] if args.engine else list(REGISTRY)
    failures = 0
    for name in targets:
        try:
            ok = engines.available(name)
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"  [{name}] check crashed: {e}")
        status = REGISTRY[name]["status"]
        print(f"{'OK  ' if ok else 'MISS'}  {name} ({status})")
        if not ok and REGISTRY[name]["kind"] == "module":
            print(f"      -> python -m engines install {name}")
            failures += 1
    return 1 if (args.engine and failures) else 0


def _cmd_install(args) -> int:
    from engines import provision
    ok = provision.install(args.engine)
    if ok:
        ok = engines.available(args.engine)
        print(f"[install] {args.engine}: "
              f"{'available' if ok else 'STILL UNAVAILABLE after install'}")
    return 0 if ok else 1


def _cmd_demo(args) -> int:
    t0 = time.time()
    if args.engine == "kenburns":
        from engines.still_motion import maybe_kenburns
        result = maybe_kenburns(args.image, args.out, args.duration,
                                size=(args.width, args.height))
    elif args.engine == "parallax":
        from engines.parallax import maybe_parallax
        result = maybe_parallax(args.image, args.out, args.duration,
                                size=(args.width, args.height))
    else:
        print(f"no demo for {args.engine!r} (choices: kenburns, parallax)")
        return 2
    if result is None:
        print("demo failed (see messages above)")
        return 1
    print(f"wrote {result} in {time.time() - t0:.1f}s")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m engines",
                                description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sp = sub.add_parser("info")
    sp.add_argument("engine")
    sp = sub.add_parser("doctor")
    sp.add_argument("engine", nargs="?")
    sp = sub.add_parser("install")
    sp.add_argument("engine")
    sp = sub.add_parser("demo")
    sp.add_argument("engine", choices=["kenburns", "parallax"])
    sp.add_argument("--image", required=True)
    sp.add_argument("--out", required=True)
    sp.add_argument("--duration", type=float, default=4.0)
    sp.add_argument("--width", type=int, default=1080)
    sp.add_argument("--height", type=int, default=1920)
    args = p.parse_args(argv)
    return {"list": _cmd_list, "info": _cmd_info, "doctor": _cmd_doctor,
            "install": _cmd_install, "demo": _cmd_demo}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
