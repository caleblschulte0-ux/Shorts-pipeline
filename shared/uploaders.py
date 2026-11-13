"""Auto-upload built shorts to monetized platforms.

Each Uploader subclass reads credentials from environment, posts the file,
and returns the public URL of the new post. Used from make_short.py via
the --upload flag.

Required environment variables per platform:

  youtube:
    Either inline JSON in env (best for Claude Code on the web — values
    persist across container recycles) or file paths (best for laptop /
    server). Inline wins if both are set.

    YOUTUBE_CLIENT_SECRETS_JSON  full client_secret.json contents
    YOUTUBE_TOKEN_JSON           full token.json contents
    -- or --
    YOUTUBE_CLIENT_SECRETS       path to client_secret.json
    YOUTUBE_TOKEN                path to writable token.json

  tiktok:
    Normally NOTHING: connect the account once at
    https://shorts-media.netlify.app/app/ and a GitHub Actions job on main
    with `permissions: id-token: write` fetches a fresh access token from
    that site (tiktok_app/, OIDC-authenticated; the site refreshes it).
    TIKTOK_HANDLE_<CHANNEL>   which linked account a channel posts to
                              (optional when exactly one is linked).
    TIKTOK_ACCESS_TOKEN[_<CHANNEL>]  a static token still wins if set, but
                              it expires in 24h — the broker does not.

  instagram / facebook (both share the Meta token):
    META_ACCESS_TOKEN[_<CHANNEL>]  Business-portfolio system-user token.
    Account ids come from channels.<id>.meta in config/channel_registry.json
    (scripts/meta_post_release.py, meta_due.yml). No public file host needed.

  rumble:
    RUMBLE_API_KEY          Partner Program API key (Rumble's public
                            upload endpoint is gated to partners).
"""
from __future__ import annotations

import os
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


class UploadError(RuntimeError):
    """Raised when an upload destination rejects or can't be configured."""


@dataclass
class UploadResult:
    platform: str
    url: str
    raw: dict = field(default_factory=dict)


class Uploader:
    name: str = "uploader"

    def upload(
        self,
        file_path: Path,
        *,
        title: str,
        description: str,
        tags: list[str] | None = None,
        publish_at: str | None = None,
    ) -> UploadResult:
        """Push a file. publish_at, if set, is an RFC3339 timestamp
        ("2026-05-29T13:00:00Z") at which the post should go public —
        platforms that support scheduling honor it; others ignore it."""
        raise NotImplementedError


def _env(key: str) -> str:
    v = os.environ.get(key)
    if not v:
        raise UploadError(f"missing env var: {key}")
    return v


def _clean_secret_strings(obj):
    """Defensive cleanup for values that came through a phone keyboard
    paste — strip stray whitespace and brackets that sometimes get
    prepended/appended."""
    if isinstance(obj, dict):
        return {k: _clean_secret_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_secret_strings(v) for v in obj]
    if isinstance(obj, str):
        return obj.strip(" \t\r\n<>\"'")
    return obj


def _resolve_secret(path_env: str, json_env: str, target_name: str) -> Path:
    """Return a Path to a JSON file containing the secret.

    Prefers the inline content env var (_JSON suffix) so credentials can
    live in the Claude Code environment settings and survive container
    recycles. Falls back to a literal file path env var for laptop /
    server use.

    Defensive: strips stray whitespace and angle brackets from every
    string value in the JSON before writing it to disk, so a phone-paste
    typo doesn't break the entire upload chain.
    """
    import json as _json
    content = os.environ.get(json_env)
    if content:
        try:
            cleaned = _json.dumps(_clean_secret_strings(_json.loads(content)))
        except Exception:
            cleaned = content
        path = Path("/tmp") / target_name
        path.write_text(cleaned)
        return path
    path = os.environ.get(path_env)
    if path:
        return Path(path)
    raise UploadError(f"missing env var: {json_env} or {path_env}")


# ---------- YouTube Shorts ----------

class YouTubeUploader(Uploader):
    name = "youtube"
    # Accept either the narrow upload scope (Desktop OAuth flow) or the
    # broader youtube scope (device-flow flow on TV/Limited Input clients,
    # which Google does not permit youtube.upload for). Both authorize
    # videos.insert.
    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
        # Read-only deep metrics (avg view %, retention curves). A re-auth via
        # setup_youtube.py grants it; existing tokens degrade gracefully.
        "https://www.googleapis.com/auth/yt-analytics.readonly",
    ]

    def __init__(self, channel: str = ""):
        """`channel` is an optional slug for multi-channel routing.
        Empty (the default) uses the original `YOUTUBE_TOKEN_JSON`
        secret — the baller_bro_2_0 channel. A non-empty value like
        "explainer" reads `YOUTUBE_TOKEN_JSON_EXPLAINER` instead so each
        channel gets its own refresh token. The client_secret stays
        shared across all channels (it's the same OAuth app)."""
        self.channel = (channel or "").strip().lower()

    def _credentials(self):
        """Load (and refresh) the OAuth credentials for this channel. Split
        out of `_service` so other clients (e.g. the youtubeAnalytics service)
        can reuse the exact same token without duplicating the auth dance."""
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
        except ImportError as e:
            raise UploadError(
                "missing python deps for youtube upload: "
                f"{e}. install with: pip install "
                "google-api-python-client google-auth google-auth-oauthlib"
            )

        client_secrets = str(_resolve_secret(
            "YOUTUBE_CLIENT_SECRETS", "YOUTUBE_CLIENT_SECRETS_JSON",
            "yt_client_secret.json",
        ))
        # Per-channel token env vars are suffixed with the upper-case
        # channel slug so the routine + CI secrets stay aligned: an
        # `"explainer"` package looks up `YOUTUBE_TOKEN_JSON_EXPLAINER`.
        # The default (empty channel) hits the original
        # `YOUTUBE_TOKEN_JSON` so the migration is backward-compatible.
        suffix = f"_{self.channel.upper()}" if self.channel else ""
        token_path_env = f"YOUTUBE_TOKEN{suffix}"
        token_json_env = f"YOUTUBE_TOKEN_JSON{suffix}"
        token_file_name = (f"yt_token_{self.channel}.json"
                           if self.channel else "yt_token.json")
        token_path = _resolve_secret(
            token_path_env, token_json_env, token_file_name,
        )
        creds = None
        if token_path.exists():
            # scopes=None makes the loader read the scopes the token was
            # actually minted with — passing self.SCOPES would force a
            # refresh that asks for whichever scope is missing and Google
            # rejects with invalid_scope.
            creds = Credentials.from_authorized_user_file(str(token_path))
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # First-run path: needs a local browser. The setup_youtube.py
                # script handles the headless / phone case via device flow.
                flow = InstalledAppFlow.from_client_secrets_file(client_secrets, self.SCOPES)
                creds = flow.run_local_server(port=0, open_browser=False)
            token_path.write_text(creds.to_json())
        return creds

    def _service(self):
        from googleapiclient.discovery import build
        return build("youtube", "v3", credentials=self._credentials())

    def analytics_service(self):
        """A youtubeAnalytics v2 client on the same token. Returns None if the
        token wasn't minted with the analytics scope, so callers can degrade
        gracefully to the public Data API (view counts only)."""
        from googleapiclient.discovery import build
        creds = self._credentials()
        scopes = set(getattr(creds, "scopes", None) or [])
        ANALYTICS = "https://www.googleapis.com/auth/yt-analytics.readonly"
        # When the token lists no scopes we optimistically try anyway and let
        # the first API call surface a 403; only skip when we KNOW it's absent.
        if scopes and ANALYTICS not in scopes and \
                "https://www.googleapis.com/auth/youtube" not in scopes:
            return None
        return build("youtubeAnalytics", "v2", credentials=creds)

    def whoami(self, svc=None) -> dict:
        """Return {'id', 'title', 'handle'} for the channel this token maps to.
        Read-only — used to confirm identity before any upload."""
        svc = svc or self._service()
        try:
            resp = svc.channels().list(part="snippet", mine=True).execute()
            items = resp.get("items", [])
            if not items:
                raise UploadError("youtube: token authorizes no channel")
            sn = items[0]["snippet"]
            return {"id": items[0]["id"], "title": sn.get("title", ""),
                    "handle": sn.get("customUrl", "")}
        except UploadError:
            raise
        except Exception as e:  # noqa: BLE001
            raise UploadError(f"youtube: could not verify channel: {e}")

    def _guard_channel(self, svc):
        """Safety: refuse to post unless the authenticated channel matches
        YOUTUBE_EXPECTED_CHANNEL (a channel title, id, or @handle). Prevents
        this repo from ever posting to the wrong account if the wrong token
        is present. No-op (but prints who it is) when the env var is unset."""
        me = self.whoami(svc)
        cid, ctitle, handle = me["id"], me["title"], me["handle"]
        expected = os.environ.get("YOUTUBE_EXPECTED_CHANNEL", "").strip()
        print(f"[youtube] authenticated channel: {ctitle!r} "
              f"handle={handle!r} ({cid})", flush=True)
        known = {ctitle.lower(), cid.lower(), handle.lower().lstrip("@")}
        if expected and expected.lower().lstrip("@") not in known:
            raise UploadError(
                f"youtube: refusing to upload — authenticated channel "
                f"{ctitle!r} ({cid}) does not match YOUTUBE_EXPECTED_CHANNEL="
                f"{expected!r}. (Guard against posting to the wrong account.)"
            )

    def upload(self, file_path, *, title, description, tags=None, publish_at=None,
               thumbnail=None, localizations=None, default_language="en",
               audio_language=None, category="22", captions_srt=None,
               synthetic_media=False):
        try:
            from googleapiclient.http import MediaFileUpload
        except ImportError as e:
            raise UploadError(
                "missing python deps for youtube upload: "
                f"{e}. install with: pip install "
                "google-api-python-client google-auth google-auth-oauthlib"
            )

        svc = self._service()
        self._guard_channel(svc)
        # YouTube requires privacyStatus=private when publishAt is set; the
        # video flips to public automatically at that timestamp.
        status = {
            "privacyStatus": "private" if publish_at else "public",
            "selfDeclaredMadeForKids": False,
            # Altered/synthetic disclosure: OFF on every channel (operator,
            # 2026-10-16: "I don't want to see AI tags on any of our stuff").
            # YouTube requires it only for realistic content a viewer could
            # mistake for real footage or a real person; Twitch and sports
            # clips are real footage and the explainer is illustrated
            # animation. Pass synthetic_media=True for anything realistic.
            "containsSyntheticMedia": bool(synthetic_media),
        }
        if publish_at:
            status["publishAt"] = publish_at
        # Auto-localize: when the caller doesn't supply translations, generate
        # them here so EVERY post on EVERY channel surfaces in search and
        # recommendations worldwide — all on one video. Pass localizations={}
        # to opt out. Best-effort: a translation hiccup never blocks the upload.
        if localizations is None:
            try:
                from shared.localize import translate_metadata
                localizations = translate_metadata(title, description)
            except Exception as e:  # noqa: BLE001
                print(f"[youtube] auto-localize skipped: {e}", flush=True)
                localizations = {}
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": list(tags or [])[:30],
                "categoryId": str(category),  # default 22 People & Blogs
                # Required for localizations to take effect; declares the base
                # language of the snippet above.
                "defaultLanguage": default_language,
                # Declares the spoken-audio language so YouTube labels the track
                # correctly and the video is eligible for auto-dubbing and the
                # manual Studio alternate-audio-track workflow.
                "defaultAudioLanguage": audio_language or default_language,
            },
            "status": status,
        }
        # Localized titles/descriptions: the same Short surfaces in search and
        # recommendations for viewers in each language. {} ships English only.
        part = "snippet,status"
        if localizations:
            body["localizations"] = {
                code: {"title": loc["title"][:100],
                       "description": loc["description"][:5000]}
                for code, loc in localizations.items()
            }
            part = "snippet,status,localizations"
        media = MediaFileUpload(
            str(file_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=8 * 1024 * 1024,
        )
        req = svc.videos().insert(part=part, body=body, media_body=media)
        response = None
        while response is None:
            _, response = req.next_chunk()
        vid = response["id"]

        # Custom thumbnail (packaging) — best-effort: a thumbnail failure must
        # never lose an already-uploaded video. Needs the channel to be
        # thumbnail-eligible (verified phone), else YouTube 403s and we skip.
        if thumbnail and Path(str(thumbnail)).exists():
            try:
                svc.thumbnails().set(
                    videoId=vid,
                    media_body=MediaFileUpload(str(thumbnail), mimetype="image/jpeg"),
                ).execute()
                print(f"[youtube] set custom thumbnail for {vid}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[youtube] thumbnail skipped for {vid}: {e}", flush=True)

        # Uploaded captions (accessibility + search + the base for YouTube's
        # auto-translated subtitles in every language). Best-effort: needs the
        # youtube.force-ssl scope — tokens minted before that scope was added
        # 403 here and we skip without losing the upload.
        if captions_srt and Path(str(captions_srt)).exists():
            try:
                svc.captions().insert(
                    part="snippet",
                    body={"snippet": {"videoId": vid,
                                      "language": default_language,
                                      "name": ""}},
                    media_body=MediaFileUpload(str(captions_srt),
                                               mimetype="application/octet-stream"),
                ).execute()
                print(f"[youtube] uploaded captions for {vid}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[youtube] captions skipped for {vid} (re-mint the "
                      f"token with youtube.force-ssl to enable): {e}",
                      flush=True)

        return UploadResult(self.name, f"https://youtube.com/shorts/{vid}", response)


# ---------- TikTok ----------

#: The Shorts Media site (tiktok_app/) holds the linked accounts and
#: refreshes their tokens; a GitHub Actions OIDC token is the only key.
TIKTOK_BROKER = "https://shorts-media.netlify.app/api/tiktok/token"
CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"


def tiktok_broker_available() -> bool:
    """True inside a GitHub Actions job granted `id-token: write`."""
    return bool(os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL")
                and os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN"))


def _tiktok_broker_auth() -> dict:
    """This job's GitHub OIDC token, as the site's Authorization header."""
    import requests
    if not tiktok_broker_available():
        raise UploadError(
            "no TikTok token: set TIKTOK_ACCESS_TOKEN, or run in GitHub "
            "Actions with `permissions: id-token: write` so the job can "
            "fetch one from shorts-media.netlify.app")
    r = requests.get(os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"],
                     params={"audience": TIKTOK_BROKER},
                     headers={"Authorization": "Bearer "
                              + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]},
                     timeout=30)
    if not r.ok:
        raise UploadError(f"github oidc token failed: {r.status_code} {r.text}")
    return {"Authorization": "Bearer " + r.json()["value"]}


def tiktok_linked_accounts(auth: dict | None = None) -> list[dict]:
    """Every account linked at shorts-media.netlify.app/app/:
    [{open_id, handle, name, scopes}] (no tokens)."""
    import requests
    r = requests.get(TIKTOK_BROKER.rsplit("/", 1)[0] + "/accounts",
                     headers=auth or _tiktok_broker_auth(), timeout=30)
    if not r.ok:
        raise UploadError(f"tiktok broker accounts failed: {r.status_code} {r.text}")
    return r.json().get("accounts") or []


def _tiktok_broker_token(channel: str = "") -> str:
    """A fresh TikTok access token for the account linked at
    shorts-media.netlify.app/app/, fetched with this job's GitHub OIDC
    token. The site only answers jobs on caleblschulte0-ux/Shorts-pipeline
    main. Which account: TIKTOK_HANDLE_<CHANNEL>, else the channel's
    `tiktok.handle` in config/channel_registry.json, else TIKTOK_HANDLE, else
    the only linked account (more than one linked and none named refuses,
    rather than guessing which account a channel posts to)."""
    import requests
    auth = _tiktok_broker_auth()

    handle = ""
    if channel:
        from shared.crosspost import tiktok_handle
        handle = tiktok_handle(channel)
    handle = (handle or os.environ.get("TIKTOK_HANDLE", "")).strip().lstrip("@")
    if handle:
        who = {"handle": handle}
    else:
        linked = tiktok_linked_accounts(auth)
        if len(linked) != 1:
            raise UploadError(
                f"{len(linked)} TikTok accounts are linked at "
                "shorts-media.netlify.app/app/ — "
                + ("connect one there" if not linked else
                   f"set repo variable TIKTOK_HANDLE_{(channel or 'X').upper()} "
                   "to the handle this channel posts to: "
                   + ", ".join("@" + (a.get("handle") or "?") for a in linked)))
        who = {"open_id": linked[0]["open_id"]}
    r = requests.post(TIKTOK_BROKER, headers=auth, json=who, timeout=30)
    if not r.ok:
        raise UploadError(f"tiktok broker token failed: {r.status_code} {r.text}"
                          + (" — reconnect the account at "
                             "shorts-media.netlify.app/app/"
                             if r.status_code == 409 else ""))
    return r.json()["access_token"]


TIKTOK_MAX_HASHTAGS = 5   # operator, 2026-10-09: "only 5 hashtags"


def cap_hashtags(caption: str, n: int = TIKTOK_MAX_HASHTAGS) -> str:
    """Keep the first n distinct #hashtags of a caption, drop the rest."""
    import re
    seen: list[str] = []

    def keep(m):
        tag = m.group(0).lower()
        if tag in seen:
            return ""
        if len(seen) >= n:
            return ""
        seen.append(tag)
        return m.group(0)
    out = re.sub(r"(?<!\S)#\w+", keep, caption)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return "\n".join(line.rstrip() for line in out.split("\n")).strip()


class TikTokUploader(Uploader):
    name = "tiktok"
    INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"

    def __init__(self, channel: str = ""):
        """`channel` routes to a per-channel access token, mirroring
        YouTubeUploader: channel="third" reads TIKTOK_ACCESS_TOKEN_THIRD and
        falls back to the shared TIKTOK_ACCESS_TOKEN."""
        self.channel = (channel or "").strip().lower()

    def _token(self) -> str:
        if self.channel:
            scoped = os.environ.get(f"TIKTOK_ACCESS_TOKEN_{self.channel.upper()}")
            if scoped:
                return scoped.strip(" \t\r\n<>\"'")
        if os.environ.get("TIKTOK_ACCESS_TOKEN"):
            return _env("TIKTOK_ACCESS_TOKEN")
        return _tiktok_broker_token(self.channel)

    def _creator_privacy(self, token: str) -> list[str]:
        """The privacy levels TikTok offers this account right now. Direct
        Post must pick from these (a value outside them is refused)."""
        import requests
        r = requests.post(CREATOR_INFO_URL, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8"}, json={},
            timeout=30)
        if not r.ok:
            raise UploadError(f"tiktok creator_info failed: {r.status_code} {r.text}")
        return list((r.json().get("data") or {}).get("privacy_level_options") or [])

    def upload(self, file_path, *, title, description, tags=None, publish_at=None):
        import requests

        # TikTok's Content Posting API doesn't expose scheduled publish via
        # the Direct Post endpoint yet; publish_at is ignored.
        token = self._token()
        size = file_path.stat().st_size
        chunk_size = min(size, 64 * 1024 * 1024)
        chunks = (size + chunk_size - 1) // chunk_size

        # The description carries the streamer credit + source link (the
        # credit+takedown doctrine now lives in the caption, not an on-screen
        # watermark). Lead with the title, then the full description (which
        # already includes the hashtags); fall back to title + tags when no
        # description is supplied.
        if description:
            caption = (title + "\n\n" + description)[:2200]
        else:
            caption = (title + " "
                       + " ".join(f"#{t}" for t in (tags or [])))[:2200]
        caption = cap_hashtags(caption)
        options = self._creator_privacy(token)
        privacy = ("PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in options
                   else "SELF_ONLY")
        init_payload = {
            "post_info": {
                "title": caption,
                "privacy_level": privacy,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": chunk_size,
                "total_chunk_count": chunks,
            },
        }
        r = requests.post(
            self.INIT_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json=init_payload,
            timeout=60,
        )
        if not r.ok and "unaudited_client" in r.text and privacy != "SELF_ONLY":
            # Until TikTok audits the app for public Direct Post, every API
            # post is private. Say so loudly — a private post is not reach —
            # and post it Only-me rather than lose the clip.
            print("::warning::[tiktok] the Shorts Media app is not yet "
                  "audited for public posting, so TikTok only accepts "
                  "private (Only me) posts. Posting privately. Request the "
                  "Content Posting API audit in the TikTok developer portal.",
                  flush=True)
            init_payload["post_info"]["privacy_level"] = privacy = "SELF_ONLY"
            r = requests.post(self.INIT_URL, headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8"},
                json=init_payload, timeout=60)
        if not r.ok:
            raise UploadError(f"tiktok init failed: {r.status_code} {r.text}")
        data = r.json().get("data", {})
        upload_url = data.get("upload_url")
        publish_id = data.get("publish_id")
        if not upload_url or not publish_id:
            raise UploadError(f"tiktok init returned unexpected payload: {r.text}")

        with open(file_path, "rb") as f:
            offset = 0
            for i in range(chunks):
                blob = f.read(chunk_size)
                end = offset + len(blob) - 1
                hdr = {
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(blob)),
                    "Content-Range": f"bytes {offset}-{end}/{size}",
                }
                r2 = requests.put(upload_url, headers=hdr, data=blob, timeout=600)
                if r2.status_code not in (200, 201, 206):
                    raise UploadError(
                        f"tiktok chunk {i + 1}/{chunks} failed: "
                        f"{r2.status_code} {r2.text}"
                    )
                offset = end + 1
        # TikTok finalizes asynchronously; the publish_id is the handle.
        return UploadResult(
            self.name,
            f"https://www.tiktok.com/@me/video/{publish_id}",
            {"publish_id": publish_id,
             "privacy_level": init_payload["post_info"]["privacy_level"]},
        )


# ---------- Meta (Instagram + Facebook Reels) ----------
#
# One token for every channel: a Business-portfolio SYSTEM USER token
# (business.facebook.com > Settings > Users > System users > Generate token),
# which never expires and needs no App Review for accounts the business owns.
# Scopes: instagram_basic, instagram_content_publish, pages_show_list,
# pages_read_engagement, pages_manage_posts, business_management.
# META_ACCESS_TOKEN_<CHANNEL> overrides it for one channel.
#
# Both uploads send the file's BYTES to rupload.facebook.com, so Meta never
# has to fetch it from a public URL (the old REELS_PUBLIC_HOST requirement
# is gone). Facebook Pages publish through /{page}/video_reels with the
# Page's own token; Instagram through a resumable REELS container.

META_GRAPH_VERSION = "v21.0"
META_GRAPH = f"https://graph.facebook.com/{META_GRAPH_VERSION}"


def meta_token(channel: str = "") -> str:
    if channel:
        v = os.environ.get(f"META_ACCESS_TOKEN_{channel.upper()}", "").strip()
        if v:
            return v
    return _env("META_ACCESS_TOKEN").strip()


def _meta_check(r, what: str) -> dict:
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:300]}
    if not r.ok or (isinstance(body, dict) and body.get("error")):
        raise UploadError(f"{what} failed: {r.status_code} {str(body)[:500]}")
    return body


def _caption(description: str, tags) -> str:
    caption = description or ""
    if tags:
        caption += "\n\n" + " ".join(f"#{t}" for t in list(tags)[:5])
    return caption


class _MetaReelsUploader(Uploader):
    GRAPH = META_GRAPH

    def __init__(self, channel: str = "", target_id: str = ""):
        self.channel = channel
        self.target = target_id

    def _rupload(self, url: str, file_path: Path, token: str) -> dict:
        import requests
        size = Path(file_path).stat().st_size
        with open(file_path, "rb") as f:
            r = requests.post(url, data=f, timeout=900, headers={
                "Authorization": f"OAuth {token}",
                "offset": "0", "file_size": str(size),
                "Content-Type": "application/octet-stream"})
        return _meta_check(r, f"{self.name} byte upload")


class InstagramUploader(_MetaReelsUploader):
    name = "instagram"

    def upload(self, file_path, *, title, description, tags=None, publish_at=None):
        import requests
        token = meta_token(self.channel)
        ig = self.target or _env("IG_USER_ID")
        c = _meta_check(requests.post(f"{self.GRAPH}/{ig}/media", timeout=60, data={
            "media_type": "REELS", "upload_type": "resumable",
            "caption": _caption(description, tags)[:2200],
            "share_to_feed": "true", "access_token": token}),
            "instagram container create")
        cid = c["id"]
        self._rupload(c.get("uri") or
                      f"https://rupload.facebook.com/ig-api-upload/"
                      f"{META_GRAPH_VERSION}/{cid}", file_path, token)
        deadline, last = time.time() + 900, None
        while time.time() < deadline:
            time.sleep(10)
            s = requests.get(f"{self.GRAPH}/{cid}", timeout=30, params={
                "fields": "status_code,status", "access_token": token})
            body = s.json() if s.ok else {}
            last = body.get("status_code")
            if last == "FINISHED":
                break
            if last in ("ERROR", "EXPIRED"):
                raise UploadError(f"instagram container {last}: {body}")
        else:
            raise UploadError(f"instagram container not FINISHED in 15m ({last})")
        p = _meta_check(requests.post(f"{self.GRAPH}/{ig}/media_publish", timeout=60,
                                      data={"creation_id": cid, "access_token": token}),
                        "instagram publish")
        media_id = p["id"]
        link = f"https://www.instagram.com/"
        try:
            q = requests.get(f"{self.GRAPH}/{media_id}", timeout=30, params={
                "fields": "permalink", "access_token": token}).json()
            link = q.get("permalink") or link
        except Exception:  # noqa: BLE001
            pass
        return UploadResult(self.name, link, {"media_id": media_id})


class FacebookUploader(_MetaReelsUploader):
    name = "facebook"

    def _page_token(self, page: str, token: str) -> str:
        import requests
        body = _meta_check(requests.get(f"{self.GRAPH}/{page}", timeout=30, params={
            "fields": "access_token", "access_token": token}), "facebook page token")
        return body.get("access_token") or token

    def upload(self, file_path, *, title, description, tags=None, publish_at=None):
        import requests
        page = self.target or _env("FB_PAGE_ID")
        token = self._page_token(page, meta_token(self.channel))
        st = _meta_check(requests.post(f"{self.GRAPH}/{page}/video_reels", timeout=60,
                                       data={"upload_phase": "start",
                                             "access_token": token}),
                         "facebook reel start")
        vid = st["video_id"]
        self._rupload(st.get("upload_url") or
                      f"https://rupload.facebook.com/video-upload/"
                      f"{META_GRAPH_VERSION}/{vid}", file_path, token)
        _meta_check(requests.post(f"{self.GRAPH}/{page}/video_reels", timeout=120, data={
            "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
            "title": (title or "")[:255],
            "description": _caption(description, tags)[:5000],
            "access_token": token}), "facebook reel publish")
        return UploadResult(self.name, f"https://www.facebook.com/reel/{vid}/",
                            {"video_id": vid})


# ---------- Rumble ----------

class RumbleUploader(Uploader):
    name = "rumble"
    UPLOAD_URL = "https://rumble.com/api/Upload.php"

    def upload(self, file_path, *, title, description, tags=None, publish_at=None):
        import requests

        api_key = _env("RUMBLE_API_KEY")
        # Rumble's API doesn't accept a scheduled publish time; ignored.
        with open(file_path, "rb") as fh:
            files = {"Filedata": (file_path.name, fh, "video/mp4")}
            data = {
                "api_key": api_key,
                "title": title[:140],
                "description": description[:1000],
                "tags": ",".join(tags or []),
                "visibility": "public",
            }
            r = requests.post(self.UPLOAD_URL, data=data, files=files, timeout=900)
        if not r.ok:
            raise UploadError(f"rumble upload failed: {r.status_code} {r.text}")
        try:
            body = r.json()
        except ValueError:
            body = {"raw": r.text}
        url = body.get("url") or body.get("video_url") or r.text.strip()
        return UploadResult(self.name, url, body)


# ---------- Registry + entry point ----------

REGISTRY: dict[str, type[Uploader]] = {
    "youtube": YouTubeUploader,
    "tiktok": TikTokUploader,
    "instagram": InstagramUploader,
    "facebook": FacebookUploader,
    "rumble": RumbleUploader,
}


def upload_to(
    targets: Iterable[str],
    file_path: Path,
    *,
    title: str,
    description: str,
    tags: list[str] | None = None,
    publish_at: str | None = None,
) -> list[UploadResult]:
    """Run uploaders sequentially. Per-target failures are reported and
    do not abort the rest of the batch."""
    results: list[UploadResult] = []
    for raw in targets:
        name = raw.strip().lower()
        if not name:
            continue
        cls = REGISTRY.get(name)
        if not cls:
            print(f"[upload] unknown target: {name!r} (have {sorted(REGISTRY)})")
            continue
        try:
            res = cls().upload(
                file_path,
                title=title,
                description=description,
                tags=tags,
                publish_at=publish_at,
            )
            print(f"[upload] {res.platform}: {res.url}")
            results.append(res)
        except UploadError as e:
            print(f"[upload] {name} failed: {e}")
        except Exception as e:  # noqa: BLE001 — surface anything else
            print(f"[upload] {name} crashed: {type(e).__name__}: {e}")
    return results
