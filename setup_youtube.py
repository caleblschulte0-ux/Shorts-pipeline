#!/usr/bin/env python3
"""One-command YouTube auto-upload setup.

Run this once on the machine you'll upload from. It opens each Google
Cloud Console page Google requires you to click through, waits for the
client_secret.json to land in your Downloads folder, signs you in, and
saves the refresh token.

After it finishes, the pipeline can auto-upload with:

    python make_short.py URL --script "..." --upload youtube

Re-runs are safe — if the existing token still works the script exits
immediately. Delete client_secret.json + token.json to force a redo.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parent
CLIENT_SECRETS = REPO / "client_secret.json"
TOKEN_PATH = REPO / "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def step(num: int, total: int, title: str) -> None:
    bar = "=" * 64
    print(f"\n{bar}\n[{num}/{total}] {title}\n{bar}")


def open_in_browser(url: str) -> None:
    print(f"  opening: {url}")
    try:
        if not webbrowser.open(url, new=2):
            print("  (couldn't auto-open — copy the URL into your browser)")
    except Exception:
        print("  (couldn't auto-open — copy the URL into your browser)")


def confirm(prompt: str) -> None:
    input(f"\n  >>> {prompt}\n  press Enter when done ")


def find_downloaded_secret(timeout: float) -> Path | None:
    download_dirs = [Path.home() / "Downloads", Path.home() / "downloads"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        for base in download_dirs:
            if not base.exists():
                continue
            cands = sorted(
                base.glob("client_secret*.json"),
                key=lambda p: -p.stat().st_mtime,
            )
            if cands and (time.time() - cands[0].stat().st_mtime) > 1:
                return cands[0]
        time.sleep(1)
    return None


def ensure_deps() -> None:
    try:
        import google_auth_oauthlib  # noqa: F401
        import googleapiclient  # noqa: F401
        return
    except ImportError:
        pass
    print("\n  Installing Google libraries (one-time)...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "-q",
        "google-api-python-client", "google-auth", "google-auth-oauthlib",
    ])


def has_local_browser() -> bool:
    if os.name == "nt" or sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def already_configured() -> bool:
    if not (CLIENT_SECRETS.exists() and TOKEN_PATH.exists()):
        return False
    try:
        ensure_deps()
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json())
        svc = build("youtube", "v3", credentials=creds)
        items = svc.channels().list(part="snippet", mine=True).execute().get("items", [])
        if items:
            print(f"already configured for channel: {items[0]['snippet']['title']}")
            return True
    except Exception as e:  # noqa: BLE001
        print(f"existing config not valid ({type(e).__name__}: {e}) — re-running setup")
    return False


def main() -> int:
    if already_configured():
        print("\nNothing to do. Delete client_secret.json + token.json to re-run.")
        return 0

    print(
        "YouTube auto-upload one-time setup\n"
        "----------------------------------\n"
        "Google requires you to click through 4 Cloud Console pages before any\n"
        "code can upload to your channel. This script opens each page for you,\n"
        "waits while you click, then takes care of the rest. ~5 minutes total.\n"
        "\n"
        "You need: a Google account that owns the channel you want to upload to."
    )
    input("\nPress Enter to start (Ctrl-C to bail).")

    step(1, 5, "Create a Google Cloud project")
    print("  - Name it anything (e.g. 'shorts-pipeline').")
    print("  - After it's created, make sure it's selected at the top of the page.")
    open_in_browser("https://console.cloud.google.com/projectcreate")
    confirm("Project created and selected.")

    step(2, 5, "Enable the YouTube Data API v3")
    print("  - Click the blue ENABLE button.")
    open_in_browser("https://console.cloud.google.com/apis/library/youtube.googleapis.com")
    confirm("API enabled.")

    step(3, 5, "Configure the OAuth consent screen")
    print(
        "  - User Type: External -> Create\n"
        "  - App name: anything; support + developer email: your email\n"
        "  - Save and Continue through 'Scopes' (nothing to add)\n"
        "  - On 'Test users', Add Users -> your own Gmail -> Save\n"
        "  - Back to Dashboard"
    )
    open_in_browser("https://console.cloud.google.com/apis/credentials/consent")
    confirm("Consent screen configured.")

    step(4, 5, "Create the OAuth client and download the JSON")
    print(
        "  - Application type: Desktop app\n"
        "  - Name: anything -> CREATE\n"
        "  - In the popup, click DOWNLOAD JSON. Don't rename the file."
    )
    open_in_browser("https://console.cloud.google.com/apis/credentials/oauthclient")
    print("\n  Waiting up to 5 minutes for client_secret*.json in your Downloads folder...")
    found = find_downloaded_secret(timeout=300)
    if not found:
        path = input("  Auto-detect failed. Paste full path to the JSON: ").strip().strip("'\"")
        found = Path(path).expanduser()
        if not found.exists():
            print(f"  ERROR: file not found: {found}")
            return 1
    shutil.copy2(found, CLIENT_SECRETS)
    print(f"  saved to {CLIENT_SECRETS}")

    step(5, 5, "Sign in to YouTube")
    ensure_deps()
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    if has_local_browser():
        print("  A browser tab will open. Pick the account that owns the channel,")
        print("  click 'Continue' on the 'app not verified' page, then 'Allow'.")
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True, prompt="consent")
    else:
        print(
            "  No local display detected. This script needs a browser on the same\n"
            "  machine. Re-run it on your laptop/desktop (where you have Chrome/Safari).\n"
            "  You can copy the saved token.json to a server afterwards."
        )
        return 2

    TOKEN_PATH.write_text(creds.to_json())
    print(f"  token saved to {TOKEN_PATH}")

    svc = build("youtube", "v3", credentials=creds)
    items = svc.channels().list(part="snippet", mine=True).execute().get("items", [])
    if items:
        print(f"\nauthorized for channel: {items[0]['snippet']['title']}")
    else:
        print("\nauthorized but this Google account has no associated YouTube channel.")
        print("Sign in with the account that owns the channel and re-run.")
        return 1

    print(
        f"\nDone. Set these once in your shell (or a .env file):\n"
        f"  export YOUTUBE_CLIENT_SECRETS={CLIENT_SECRETS}\n"
        f"  export YOUTUBE_TOKEN={TOKEN_PATH}\n"
        f"\nThen upload by adding --upload youtube to make_short.py."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
