#!/usr/bin/env python3
"""Dispatch a workflow and PROVE GitHub accepted it.

On 2026-08-23 daily.yml's `workflow_run` trigger silently failed to fire
across two successful completions of Phase B — a full zero-render day with
every check green (doctor finding 2fc5cbb21cca). The repair was to dispatch
Daily Shorts explicitly and fail the job when the API does not answer 204.

That repair lived as inline shell, and its regression test parsed the YAML
and looked for the substring `204`, a `HTTP.*!=.*204` regex, and an `exit 1`
within 400 characters of it (doctor finding d486c2fbfdaf). None of that runs
anything. A refactor could leave those tokens in a comment or an unreachable
branch while a rejected dispatch exited zero, and every assertion still
passed — a test of a critical handoff that proves the presence of strings.

So the logic lives here, where the failure modes are executable: 204,
401/403/404/422, a timeout, a malformed response, a missing token. The
workflow keeps one thin assertion that it calls this after a real,
non-dry-run apply.

    python3 scripts/dispatch_render.py --repo owner/name \\
        --workflow daily.yml --ref main --date 20260909
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"
ACCEPTED = 204
TIMEOUT = 30


class DispatchRefused(RuntimeError):
    """The API did not accept the dispatch. Carries what it said."""

    def __init__(self, status, body: str = ""):
        self.status = status
        self.body = (body or "")[:500]
        super().__init__(f"HTTP {status}: {self.body}")


def dispatch(repo: str, workflow: str, ref: str, token: str,
             *, opener=None, timeout: int = TIMEOUT) -> int:
    """POST the dispatch. Returns the HTTP status on success.

    Raises DispatchRefused on ANY answer that is not 204 — including a
    2xx that is not 204, because the documented accept code is 204 and a
    different success is a contract change we should hear about, not
    guess at.
    """
    if not token:
        raise DispatchRefused("no-token", "no API token was provided")
    req = urllib.request.Request(
        API.format(repo=repo, workflow=workflow),
        data=json.dumps({"ref": ref}).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"},
        method="POST")
    open_it = opener or urllib.request.urlopen
    try:
        with open_it(req, timeout=timeout) as r:
            status = getattr(r, "status", None) or r.getcode()
            if status != ACCEPTED:
                raise DispatchRefused(status, _read(r))
            return status
    except urllib.error.HTTPError as e:                  # 4xx / 5xx
        raise DispatchRefused(e.code, _read(e)) from e
    except DispatchRefused:
        raise
    except Exception as e:                               # noqa: BLE001
        # A timeout, a DNS failure, a reset — indistinguishable from here,
        # and all of them mean the same thing: we do not know that a render
        # was queued, so we must not report that one was.
        raise DispatchRefused("no-response", f"{type(e).__name__}: {e}") from e


def _read(resp) -> str:
    try:
        return resp.read().decode("utf-8", "replace")
    except Exception:                                    # noqa: BLE001
        return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--workflow", default="daily.yml")
    ap.add_argument("--ref", default="main")
    ap.add_argument("--date", default="")
    args = ap.parse_args(argv)

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    what = f" for {args.date}" if args.date else ""
    try:
        dispatch(args.repo, args.workflow, args.ref, token)
    except DispatchRefused as e:
        print(f"::error::{args.workflow} dispatch FAILED{what} "
              f"({e.status}): {e.body}")
        print(f"::error::Phase B applied{what} but the render handoff was "
              f"never accepted — dispatch it manually: "
              f"gh workflow run {args.workflow} --ref {args.ref}")
        return 1
    print(f"::notice::{args.workflow} explicitly dispatched{what} "
          f"(HTTP {ACCEPTED} accepted).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
