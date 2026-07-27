from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Iterator

from .contracts import (
    GeneratedPackage,
    PostingClaim,
    ProviderKind,
    QueueItem,
    QueueStatus,
    stable_id,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _package_from_dict(data: dict) -> GeneratedPackage:
    data = dict(data)
    data["provider"] = ProviderKind(data["provider"])
    from .contracts import DegradationLevel
    data["degradation"] = DegradationLevel(data["degradation"])
    return GeneratedPackage(**data)


def _item_from_dict(data: dict) -> QueueItem:
    data = dict(data)
    data["status"] = QueueStatus(data["status"])
    data["package"] = _package_from_dict(data["package"])
    return QueueItem(**data)


class ApprovedQueue:
    """File-backed queue with atomic writes and short-lived exclusive lock files."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "approved_queue.json"
        self.lock_path = self.root / ".approved_queue.lock"

    @contextmanager
    def _locked(self, *, timeout_seconds: float = 5.0) -> Iterator[None]:
        deadline = time.monotonic() + timeout_seconds
        fd: int | None = None
        while fd is None:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("approved queue lock timeout")
                time.sleep(0.02)
        try:
            os.write(fd, str(os.getpid()).encode("ascii"))
            yield
        finally:
            os.close(fd)
            self.lock_path.unlink(missing_ok=True)

    def _load(self) -> list[QueueItem]:
        if not self.index_path.exists():
            return []
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        return [_item_from_dict(item) for item in data.get("items", [])]

    def _save(self, items: list[QueueItem]) -> None:
        payload = {"schema_version": 1, "items": [asdict(item) for item in items]}
        fd, temp_name = tempfile.mkstemp(prefix="queue-", suffix=".json", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.index_path)
        finally:
            Path(temp_name).unlink(missing_ok=True)

    def items(self) -> tuple[QueueItem, ...]:
        with self._locked():
            return tuple(self._load())

    def enqueue(self, package: GeneratedPackage, *, priority: int = 100, available_at: str = "") -> QueueItem:
        if not package.postable():
            raise ValueError("only approved, QA-passed packages may enter the posting queue")
        with self._locked():
            items = self._load()
            if any(item.package.content_fingerprint == package.content_fingerprint for item in items):
                raise ValueError("duplicate_content_fingerprint")
            item = QueueItem(package=package, priority=priority, available_at=available_at)
            items.append(item)
            self._save(items)
            return item

    def claim_next(self, channel: str, *, at: str | None = None) -> PostingClaim:
        at = at or now_iso()
        with self._locked():
            items = self._load()
            candidates = [
                (index, item) for index, item in enumerate(items)
                if item.status is QueueStatus.READY
                and item.package.channel == channel
                and (not item.available_at or item.available_at <= at)
            ]
            if not candidates:
                return PostingClaim(None, "", "approved_queue_empty")
            index, selected = min(candidates, key=lambda pair: (pair[1].priority, pair[1].available_at, pair[1].queue_id))
            token = stable_id("claim", {"queue_id": selected.queue_id, "at": at, "pid": os.getpid()})
            claimed = QueueItem(**{
                **asdict(selected),
                "package": selected.package,
                "status": QueueStatus.CLAIMED,
                "claim_token": token,
                "claimed_at": at,
            })
            items[index] = claimed
            self._save(items)
            return PostingClaim(claimed, token, "claimed")

    def mark_posted(self, claim_token: str, upload_id: str, *, at: str | None = None) -> QueueItem:
        if not claim_token or not upload_id:
            raise ValueError("claim_token and upload_id are required")
        at = at or now_iso()
        with self._locked():
            items = self._load()
            for index, item in enumerate(items):
                if item.claim_token == claim_token and item.status is QueueStatus.CLAIMED:
                    updated = QueueItem(**{
                        **asdict(item),
                        "package": item.package,
                        "status": QueueStatus.POSTED,
                        "posted_at": at,
                        "upload_id": upload_id,
                    })
                    items[index] = updated
                    self._save(items)
                    return updated
            raise KeyError("active claim not found")

    def release_claim(self, claim_token: str) -> QueueItem:
        with self._locked():
            items = self._load()
            for index, item in enumerate(items):
                if item.claim_token == claim_token and item.status is QueueStatus.CLAIMED:
                    updated = QueueItem(**{
                        **asdict(item),
                        "package": item.package,
                        "status": QueueStatus.READY,
                        "claim_token": "",
                        "claimed_at": "",
                    })
                    items[index] = updated
                    self._save(items)
                    return updated
            raise KeyError("active claim not found")

    def reject(self, package_id: str, reason: str) -> QueueItem:
        with self._locked():
            items = self._load()
            for index, item in enumerate(items):
                if item.package.package_id == package_id:
                    updated = QueueItem(**{
                        **asdict(item),
                        "package": item.package,
                        "status": QueueStatus.REJECTED,
                        "rejection_reason": reason,
                    })
                    items[index] = updated
                    self._save(items)
                    return updated
            raise KeyError(package_id)
