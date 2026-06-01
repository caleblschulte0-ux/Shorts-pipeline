#!/usr/bin/env python3
"""TikTok Content Posting API demo for sandbox approval.

What it does, end-to-end on one keypress:

  1. Spins up a local HTTPS-via-localhost server to catch the OAuth
     callback (TikTok allows http://localhost on sandbox).
  2. Opens your browser to TikTok's authorization page with the
     video.publish scope.
  3. Receives the auth code on /callback, exchanges it for an access
     token.
  4. Initializes a FILE_UPLOAD video post via Content Posting API,
     uploads the bytes, polls for processing, prints the resulting
     publish_id.

Record this entire run as your demo video for TikTok app review.

Prerequisites:
  pip install requests
  export TIKTOK_CLIENT_KEY=aw9hmk3x2xmhv4mv   # from dev portal
  export TIKTOK_CLIENT_SECRET=...              # from dev portal
  python3 tiktok_demo.py path/to/some_video.mp4

Before first run, in the TikTok developer dashboard:
  - Add http://localhost:8000/callback as a redirect URI
  - Add your own TikTok handle as a sandbox tester
"""
from __future__ import annotations

import base64
import hashlib
import os
import sys
import time
import json
import secrets
import threading
import webbrowser
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY")
CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/callback"
SCOPES = "user.info.basic,video.upload,video.publish"

# Where the local server stashes the auth code so the main thread can
# grab it. Set by the request handler, read by main().
_auth_code: dict[str, str] = {}


class CallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, *_a, **_kw):  # quiet the default access log
        pass

    def do_GET(self):
        if not self.path.startswith("/callback"):
            self.send_response(404)
            self.end_headers()
            return
        qs = urllib.parse.urlparse(self.path).query
        params = dict(urllib.parse.parse_qsl(qs))
        _auth_code.update(params)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>TikTok auth received.</h1>"
                         b"<p>You can close this tab.</p>")


def _start_local_server() -> HTTPServer:
    srv = HTTPServer(("localhost", 8000), CallbackHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


def _pkce_pair() -> tuple[str, str]:
    """Generate a PKCE verifier+challenge pair. TikTok requires this
    on every authorization request — without it the auth page returns
    'Something went wrong / code_challenge'."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _build_auth_url(state: str, code_challenge: str) -> str:
    qs = urllib.parse.urlencode({
        "client_key": CLIENT_KEY,
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })
    return f"https://www.tiktok.com/v2/auth/authorize/?{qs}"


def _exchange_code(code: str, code_verifier: str) -> dict:
    """Auth code -> access token. Includes the PKCE code_verifier so
    TikTok can confirm it matches the challenge sent at auth time."""
    body = urllib.parse.urlencode({
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }).encode()
    req = urllib.request.Request(
        "https://open.tiktokapis.com/v2/oauth/token/",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _init_upload(access_token: str, file_size: int) -> dict:
    """Initialize a FILE_UPLOAD video post. Returns the publish_id and
    the chunk upload URL TikTok wants the bytes streamed to."""
    body = json.dumps({
        "post_info": {
            "title": "TikTok API demo upload",
            "privacy_level": "SELF_ONLY",      # sandbox-safe
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "video_cover_timestamp_ms": 1000,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,            # single-chunk for simplicity
            "total_chunk_count": 1,
        },
    }).encode()
    req = urllib.request.Request(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _upload_chunk(upload_url: str, video_path: Path, file_size: int) -> None:
    """PUT the entire video file to the URL TikTok handed us."""
    data = video_path.read_bytes()
    req = urllib.request.Request(
        upload_url, data=data, method="PUT",
        headers={
            "Content-Type": "video/mp4",
            "Content-Length": str(file_size),
            "Content-Range": f"bytes 0-{file_size-1}/{file_size}",
        },
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        print(f"  upload chunk: HTTP {r.status}")


def _poll_status(access_token: str, publish_id: str) -> dict:
    body = json.dumps({"publish_id": publish_id}).encode()
    req = urllib.request.Request(
        "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main() -> int:
    if not CLIENT_KEY or not CLIENT_SECRET:
        sys.exit("set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET first")
    if len(sys.argv) < 2:
        sys.exit("usage: tiktok_demo.py <video.mp4>")
    video_path = Path(sys.argv[1]).expanduser().resolve()
    if not video_path.exists():
        sys.exit(f"no such file: {video_path}")

    print(f"\n=== TikTok Content Posting API demo ===")
    print(f"client_key:   {CLIENT_KEY}")
    print(f"redirect_uri: {REDIRECT_URI}")
    print(f"video:        {video_path} ({video_path.stat().st_size} bytes)\n")

    # 1. Start the local callback server.
    print("[1/5] starting local OAuth callback server on :8000...")
    srv = _start_local_server()

    # 2. Open browser to TikTok auth (with PKCE).
    state = secrets.token_urlsafe(16)
    code_verifier, code_challenge = _pkce_pair()
    auth_url = _build_auth_url(state, code_challenge)
    print(f"[2/5] opening browser to TikTok auth...\n      {auth_url}\n")
    webbrowser.open(auth_url)

    # 3. Wait for the user to authorize.
    print("[3/5] waiting for user to authorize in browser...")
    while "code" not in _auth_code:
        time.sleep(0.5)
    srv.shutdown()
    if _auth_code.get("state") != state:
        sys.exit("state mismatch — possible CSRF, aborting")
    code = _auth_code["code"]
    print(f"      got auth code: {code[:12]}...")

    # 4. Exchange for access token.
    print("\n[4/5] exchanging code for access token...")
    tok = _exchange_code(code, code_verifier)
    access_token = tok.get("access_token")
    if not access_token:
        print(json.dumps(tok, indent=2))
        sys.exit("token exchange failed")
    print(f"      access_token: {access_token[:24]}...  (expires in {tok.get('expires_in')}s)")
    print(f"      open_id:      {tok.get('open_id')}")
    print(f"      scopes:       {tok.get('scope')}")

    # 5. Init upload, push bytes, poll status.
    print("\n[5/5] uploading video via Content Posting API...")
    file_size = video_path.stat().st_size
    init = _init_upload(access_token, file_size)
    data = init.get("data") or {}
    publish_id = data.get("publish_id")
    upload_url = data.get("upload_url")
    if not publish_id or not upload_url:
        print(json.dumps(init, indent=2))
        sys.exit("init failed")
    print(f"      publish_id: {publish_id}")
    print(f"      upload_url: {upload_url[:80]}...")

    _upload_chunk(upload_url, video_path, file_size)

    # Poll a couple times for status.
    for i in range(6):
        time.sleep(5)
        st = _poll_status(access_token, publish_id)
        status = (st.get("data") or {}).get("status")
        print(f"      poll {i+1}: status={status}")
        if status in ("PUBLISH_COMPLETE", "FAILED"):
            break

    print(f"\n=== done. publish_id={publish_id} ===")
    print("This recording is your demo video for TikTok app review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
