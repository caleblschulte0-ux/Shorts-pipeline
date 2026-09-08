#!/usr/bin/env python3
"""CREDENTIAL HEARTBEAT — which key is actually dead, and only when it is.

Every preflight in this repo checks whether a credential is SET. A revoked
key is a non-empty string, so it passes all of them and dies at the moment it
is needed. That is exactly how 2026-09-07 went: `GROQ_API_KEY` was present,
the workflow was green, the preflight was satisfied, and three trending slots
died on the one call that mattered.

So this makes the cheapest possible LIVE call to each credential and reports
what came back.

THE DISTINCTION THAT MATTERS IS DEAD vs LIMITED. A 401 means the key is gone
and somebody has to mint a new one. A 429 means the key is fine and the
window is spent — refreshing it changes nothing and wastes an afternoon.
Reporting both as "the key is broken" is how an operator ends up rotating
keys on a schedule to stay ahead of a problem they do not have.

It is a REPORTER. It never edits a secret, never disables a channel, and
never changes what any workflow does. `state/credentials.json` is its record,
which is also what lets the caller alert on a CHANGE rather than nagging
daily — the pipeline already learned that lesson once (daily.yml: "alerting
on it daily is how people learn to ignore the channel").

    python3 scripts/credential_check.py           # probe, print, write state
    python3 scripts/credential_check.py --json    # machine-readable
    python3 scripts/credential_check.py --offline # no network: SET/UNSET only

Exit status is 1 only when something is DEAD, so a scheduled run stays green
through a spent quota and fails the day a key actually needs replacing.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / "state" / "credentials.json"

# The five outcomes, and what each one asks of a person.
OK = "ok"                    # answered — nothing to do
DEAD = "dead"                # rejected the credential — mint a new one
LIMITED = "limited"          # quota or rate limit — the key is FINE, wait
UNSET = "unset"              # not configured here
UNREACHABLE = "unreachable"  # network/DNS/timeout — says nothing about the key

_ACTION = {
    OK: "",
    DEAD: "REPLACE THIS ONE",
    LIMITED: "nothing to do — the key is fine, the window is spent",
    UNSET: "not configured (fine if this credential is unused)",
    UNREACHABLE: "could not reach the service — try again, not a key problem",
}


def _get(url: str, headers: dict | None = None, timeout: int = 20):
    """GET, returning (http_status, body). A status code is the answer here —
    an HTTPError is data, not an exception."""
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(2000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(2000).decode("utf-8", "replace")


def _post(url: str, data: bytes, headers: dict, timeout: int = 20):
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(2000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(2000).decode("utf-8", "replace")


def classify(status: int, body: str = "") -> tuple[str, str]:
    """One HTTP status -> one verdict, for every provider.

    401/403 is the credential being refused. 429 is the credential being
    ACCEPTED and then throttled, which is the opposite conclusion. 400 is
    ambiguous in general but not here: every probe below sends a request that
    is well formed by construction, so the only thing left to be wrong with
    it is the key — Google returns 400 API_KEY_INVALID rather than 401.
    """
    if status in (401, 403):
        return DEAD, f"HTTP {status} — the credential was refused"
    if status == 429:
        return LIMITED, "HTTP 429 — rate limited or out of quota"
    if status == 400 and ("API_KEY_INVALID" in body or "api key" in body.lower()
                          or "invalid_grant" in body):
        return DEAD, "HTTP 400 — the service says the key itself is invalid"
    if 200 <= status < 300:
        return OK, f"HTTP {status}"
    if status >= 500:
        return UNREACHABLE, f"HTTP {status} — the service is having trouble"
    return UNREACHABLE, f"HTTP {status}: {body[:120]}"


def probe_groq(key: str) -> tuple[str, str]:
    return classify(*_get("https://api.groq.com/openai/v1/models",
                          {"Authorization": f"Bearer {key}"}))


def probe_gemini(key: str) -> tuple[str, str]:
    return classify(*_get(
        "https://generativelanguage.googleapis.com/v1beta/models?key=" + key))


def probe_anthropic(key: str) -> tuple[str, str]:
    return classify(*_get("https://api.anthropic.com/v1/models",
                          {"x-api-key": key,
                           "anthropic-version": "2023-06-01"}))


def probe_youtube(token_json: str) -> tuple[str, str]:
    """Ask Google to refresh the token, which is what an upload does first.

    This is the one worth probing most: a dead YouTube token does not degrade
    the day, it ends it — the video renders, passes every gate, and has
    nowhere to go.
    """
    try:
        blob = json.loads(token_json)
    except (ValueError, TypeError):
        return DEAD, "not valid JSON — the secret is malformed"
    missing = [k for k in ("refresh_token", "client_id", "client_secret")
               if not blob.get(k)]
    if missing:
        return DEAD, f"token JSON is missing {', '.join(missing)}"
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": blob["refresh_token"],
        "client_id": blob["client_id"],
        "client_secret": blob["client_secret"],
    }).encode()
    return classify(*_post(
        "https://oauth2.googleapis.com/token", body,
        {"Content-Type": "application/x-www-form-urlencoded"}))


def probe_claude_cli(_token: str) -> tuple[str, str]:
    """The subscription token is not an API key and has no cheap HTTP probe,
    so it is exercised the way the showrunner exercises it: run the CLI.

    Without the CLI installed there is nothing to say — reporting that as a
    dead token would send somebody to mint a credential that is fine.
    """
    if not shutil.which("claude"):
        return UNREACHABLE, "the claude CLI is not installed on this runner"
    try:
        proc = subprocess.run(["claude", "-p", "reply with the word ok"],
                              capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return UNREACHABLE, "the CLI did not answer within 120s"
    out = ((proc.stdout or "") + (proc.stderr or "")).lower()
    if "usage limit" in out or "rate limit" in out:
        return LIMITED, "the subscription window is spent"
    if proc.returncode == 0 and out.strip():
        return OK, "the CLI answered"
    return DEAD, f"rc={proc.returncode} {out.strip()[:120]}"


# name -> (env var, probe). Anything absent from the environment is UNSET and
# is never probed.
PROBES = (
    ("groq", "GROQ_API_KEY", probe_groq),
    ("gemini", "GEMINI_API_KEY", probe_gemini),
    ("anthropic", "ANTHROPIC_API_KEY", probe_anthropic),
    ("claude-subscription", "CLAUDE_CODE_OAUTH_TOKEN", probe_claude_cli),
)


def youtube_envs(environ=None) -> list[str]:
    """Every YouTube token in the environment, whatever the channel is called.

    Discovered rather than listed, because a hardcoded list drifts the day a
    channel is added — and the failure mode of drifting is that the new
    channel's token is the one nobody is watching.
    """
    env = os.environ if environ is None else environ
    return sorted(k for k in env
                  if k.startswith("YOUTUBE_TOKEN_JSON") and env.get(k, "").strip())


def check(offline: bool = False, environ=None) -> dict:
    env = os.environ if environ is None else environ
    rows = []
    for name, var, probe in PROBES:
        val = (env.get(var) or "").strip()
        if not val:
            rows.append({"name": name, "env": var, "status": UNSET,
                         "detail": ""})
            continue
        if offline:
            rows.append({"name": name, "env": var, "status": "set",
                         "detail": "not probed (--offline)"})
            continue
        try:
            status, detail = probe(val)
        except Exception as e:  # noqa: BLE001 — a probe must never take the run
            status, detail = UNREACHABLE, f"{type(e).__name__}: {str(e)[:120]}"
        rows.append({"name": name, "env": var, "status": status,
                     "detail": detail})
    for var in youtube_envs(env):
        chan = var[len("YOUTUBE_TOKEN_JSON"):].lstrip("_").lower() or "default"
        if offline:
            rows.append({"name": f"youtube:{chan}", "env": var,
                         "status": "set", "detail": "not probed (--offline)"})
            continue
        try:
            status, detail = probe_youtube(env[var])
        except Exception as e:  # noqa: BLE001
            status, detail = UNREACHABLE, f"{type(e).__name__}: {str(e)[:120]}"
        rows.append({"name": f"youtube:{chan}", "env": var,
                     "status": status, "detail": detail})
    return {"checked_at": __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "credentials": rows}


def changed_to_dead(report: dict, previous: dict | None) -> list[str]:
    """Which credentials are dead NOW that were not dead last time.

    The alert hangs off this, not off the dead list, because a repeated alarm
    for a known-dead key is how an operator learns to ignore the channel that
    will one day tell them something new.
    """
    was = {r["name"]: r["status"] for r in (previous or {}).get("credentials", [])}
    return [r["name"] for r in report["credentials"]
            if r["status"] == DEAD and was.get(r["name"]) != DEAD]


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--offline", action="store_true",
                    help="report SET/UNSET without calling anything")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)

    previous = _load(STATE)
    report = check(offline=args.offline)
    report["newly_dead"] = changed_to_dead(report, previous)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"credentials  {report['checked_at']}")
        for r in report["credentials"]:
            act = _ACTION.get(r["status"], "")
            print(f"  {r['status']:12s} {r['name']:22s} {r['detail'][:60]:60s}"
                  f" {act}")
        dead = [r["name"] for r in report["credentials"]
                if r["status"] == DEAD]
        print()
        if dead:
            print(f"REPLACE: {', '.join(dead)}")
        else:
            print("nothing needs replacing.")

    if not args.no_write:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(report, indent=2) + "\n")
    return 1 if any(r["status"] == DEAD for r in report["credentials"]) else 0


if __name__ == "__main__":
    sys.exit(main())
