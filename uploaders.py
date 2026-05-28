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


def _resolve_secret(path_env: str, json_env: str, target_name: str) -> Path:
    """Return a Path to a JSON file containing the secret.

    Prefers the inline content env var (_JSON suffix) so credentials can
    live in the Claude Code environment settings and survive container
    recycles. Falls back to a literal file path env var for laptop /
    server use.
    """
    content = os.environ.get(json_env)
    if content:
        path = Path("/tmp") / target_name
        path.write_text(content)
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
    ]

    def _service(self):
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
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
        token_path = _resolve_secret(
            "YOUTUBE_TOKEN", "YOUTUBE_TOKEN_JSON",
            "yt_token.json",
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
        return build("youtube", "v3", credentials=creds)

    def upload(self, file_path, *, title, description, tags=None, publish_at=None):
        try:
            from googleapiclient.http import MediaFileUpload
        except ImportError as e:
            raise UploadError(
                "missing python deps for youtube upload: "
                f"{e}. install with: pip install "
                "google-api-python-client google-auth google-auth-oauthlib"
            )

        svc = self._service()
        # YouTube requires privacyStatus=private when publishAt is set; the
        # video flips to public automatically at that timestamp.
        status = {
            "privacyStatus": "private" if publish_at else "public",
            "selfDeclaredMadeForKids": False,
        }
        if publish_at:
            status["publishAt"] = publish_at
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": list(tags or [])[:30],
                "categoryId": "22",  # People & Blogs
            },
            "status": status,
        }
        media = MediaFileUpload(
            str(file_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=8 * 1024 * 1024,
        )
        req = svc.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _, response = req.next_chunk()
        vid = response["id"]
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
