from __future__ import annotations

import copy
import hashlib
import json


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def apply_shadow_plan(story: dict, plan: dict) -> tuple[dict, dict]:
    original = copy.deepcopy(story)
    changed = copy.deepcopy(story)
    for item in plan.get("segments", []):
        idx = int(item["index"])
        changed["segments"][idx]["kind"] = item["kind"]
        changed["segments"][idx]["perf_override"] = item["perf_override"]
        changed["segments"][idx]["plan_locked"] = True
    receipt = {
        "before_hash": canonical_hash(original),
        "after_hash": canonical_hash(changed),
        "original": original,
    }
    if receipt["before_hash"] == receipt["after_hash"]:
        raise ValueError("shadow plan did not change the story")
    return changed, receipt


def restore_original(changed: dict, receipt: dict) -> dict:
    if canonical_hash(changed) != receipt.get("after_hash"):
        raise ValueError("changed state no longer matches the restoration receipt")
    restored = copy.deepcopy(receipt["original"])
    if canonical_hash(restored) != receipt.get("before_hash"):
        raise ValueError("restoration verification failed")
    return restored
