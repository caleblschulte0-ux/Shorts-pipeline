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
    TIKTOK_ACCESS_TOKEN     user access token with video.publish scope.
                            Setup: register a TikTok developer app,
                            complete Content Posting API review (~1-2
                            weeks), then run a one-time OAuth flow to
                            mint the token (refresh outside this tool).

  instagram / facebook (both share the Meta token):
    META_ACCESS_TOKEN       long-lived page/system-user token with
                            instagram_content_publish and/or
                            pages_manage_posts scopes.
    IG_USER_ID              Instagram Business / Creator account ID
                            (instagram-only).
    FB_PAGE_ID              Facebook Page ID (facebook-only).
    REELS_PUBLIC_HOST       HTTPS URL prefix Meta can fetch the file
                            from. The pipeline does NOT host it for
                            you — copy the output MP4 to S3 / R2 /
                            Cloudfront and point this at that prefix.

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
               audio_language=None, category="22", captions_srt=None):
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
            # Honest AI disclosure: this pipeline uses synthetic voiceover and
            # AI-generated imagery, so declare altered/synthetic content per
            # YouTube's disclosure policy (shows the "altered or synthetic"
            # label where YouTube deems it relevant; protects the channel).
            "containsSyntheticMedia": True,
        }
        if publish_at:
            status["publishAt"] = publish_at
        # Auto-localize: when the caller doesn't supply translations, generate
        # them here so EVERY post on EVERY channel surfaces in search and
        # recommendations worldwide — all on one video. Pass localizations={}
        # to opt out. Best-effort: a translation hiccup never blocks the upload.
        if localizations is None:
            try:
                from localize import translate_metadata
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

class TikTokUploader(Uploader):
    name = "tiktok"
    INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"

    def upload(self, file_path, *, title, description, tags=None, publish_at=None):
        import requests

        # TikTok's Content Posting API doesn't expose scheduled publish via
        # the Direct Post endpoint yet; publish_at is ignored.
        token = _env("TIKTOK_ACCESS_TOKEN")
        size = file_path.stat().st_size
        chunk_size = min(size, 64 * 1024 * 1024)
        chunks = (size + chunk_size - 1) // chunk_size

        caption = (title + " " + " ".join(f"#{t}" for t in (tags or [])))[:2200]
        init_payload = {
            "post_info": {
                "title": caption,
                "privacy_level": "PUBLIC_TO_EVERYONE",
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
            {"publish_id": publish_id},
        )


# ---------- Meta (Instagram + Facebook Reels) ----------

class _MetaReelsUploader(Uploader):
    GRAPH = "https://graph.facebook.com/v21.0"

    def _target_id(self) -> str:
        raise NotImplementedError

    def _post_url(self, post_id: str) -> str:
        raise NotImplementedError

    def upload(self, file_path, *, title, description, tags=None, publish_at=None):
        import requests

        # Meta Reels supports scheduled posting via "published=false" +
        # scheduled_publish_time on Pages, but only on FB Pages, not
        # Instagram. For now publish_at is ignored on both.
        token = _env("META_ACCESS_TOKEN")
        target = self._target_id()
        host = _env("REELS_PUBLIC_HOST")
        public_url = host.rstrip("/") + "/" + urllib.parse.quote(file_path.name)

        caption = description
        if tags:
            caption += "\n\n" + " ".join(f"#{t}" for t in tags)

        r = requests.post(
            f"{self.GRAPH}/{target}/media",
            data={
                "media_type": "REELS",
                "video_url": public_url,
                "caption": caption[:2200],
                "access_token": token,
            },
            timeout=60,
        )
        if not r.ok:
            raise UploadError(
                f"{self.name} container create failed: {r.status_code} {r.text}"
            )
        container_id = r.json()["id"]

        deadline = time.time() + 600
        last_code = None
        while time.time() < deadline:
            time.sleep(5)
            s = requests.get(
                f"{self.GRAPH}/{container_id}",
                params={"fields": "status_code", "access_token": token},
                timeout=30,
            )
            last_code = (s.json() or {}).get("status_code")
            if last_code == "FINISHED":
                break
            if last_code == "ERROR":
                raise UploadError(f"{self.name} container errored: {s.text}")
        else:
            raise UploadError(
                f"{self.name} container did not reach FINISHED in 10m "
                f"(last status={last_code})"
            )

        p = requests.post(
            f"{self.GRAPH}/{target}/media_publish",
            data={"creation_id": container_id, "access_token": token},
            timeout=60,
        )
        if not p.ok:
            raise UploadError(f"{self.name} publish failed: {p.status_code} {p.text}")
        post_id = p.json()["id"]
        return UploadResult(self.name, self._post_url(post_id), p.json())


class InstagramUploader(_MetaReelsUploader):
    name = "instagram"

    def _target_id(self):
        return _env("IG_USER_ID")

    def _post_url(self, post_id):
        return f"https://www.instagram.com/reel/{post_id}/"


class FacebookUploader(_MetaReelsUploader):
    name = "facebook"

    def _target_id(self):
        return _env("FB_PAGE_ID")

    def _post_url(self, post_id):
        return f"https://www.facebook.com/reel/{post_id}/"


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
