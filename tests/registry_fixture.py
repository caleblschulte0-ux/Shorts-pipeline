"""Point the channel registry at a temporary file, for tests.

Most tests care about MECHANISM — does the bank refuse a duplicate slug, does
ingest quarantine a broken package — not about what today's operator ruling
happens to be. Pinning those to the live registry means every future mix
change breaks fifty unrelated tests and someone edits the numbers back.

So mechanism tests run against a FIXTURE registry, and a small dedicated set
(`tests/test_channel_registry.py`) asserts the real production ruling. That
split is the whole point: change `config/channel_registry.json` and only the
tests that are ABOUT the ruling should notice.

    from tests.registry_fixture import registry

    with registry(trending={"reddit_story": 2, "text_card": 2,
                            "graph_race": 2}):
        ...                     # the code under test sees that mix
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import channel_registry as reg          # noqa: E402

#: Formats the fixture knows how to describe. Anything else must be passed
#: as a full spec dict.
_SPECS = {
    "reddit_story": {"renderer": "make_reddit_story.py",
                     "detect": {"absent": "format", "requires": "subreddit"},
                     "required_fields": ["subreddit", "slug", "title",
                                         "hashtags", "script", "shots",
                                         "punches", "music_vibe"],
                     "media": {"shots": True, "chatgpt_supplies_images": True},
                     "chatgpt_roles": ["media_worker", "editorial_review",
                                       "takeover_authoring"]},
    "text_card": {"renderer": "make_text_card.py",
                  "detect": {"field": "format", "equals": "text_card"},
                  "required_fields": ["format", "slug", "title", "duration",
                                      "broll_query", "text", "highlights",
                                      "hashtags", "music_vibe"],
                  "media": {"shots": False},
                  "chatgpt_roles": ["editorial_review",
                                    "takeover_authoring"]},
    "graph_race": {"renderer": "make_graph_race.py",
                   "detect": {"field": "format", "equals": "graph_race"},
                   "required_fields": ["format", "slug", "title", "y_label",
                                       "duration", "source", "years",
                                       "series", "hashtags", "music_vibe"],
                   "media": {"shots": False},
                   "chatgpt_roles": ["editorial_review",
                                     "takeover_authoring"]},
}


def build(trending=None, *, retired=(), channels=None, revision=1,
          extra_formats=None) -> dict:
    """A complete, valid registry from a mix dict. Keeps the fixture honest:
    it goes through the same `validate()` production does."""
    trending = dict(trending if trending is not None
                    else {"reddit_story": 2, "text_card": 2, "graph_race": 2})
    fmts = {}
    for fid, target in trending.items():
        spec = dict((extra_formats or {}).get(fid) or _SPECS.get(fid) or {})
        if not spec:
            raise ValueError(f"no fixture spec for format {fid!r} — pass one "
                             f"via extra_formats")
        spec.update({"state": "active", "target": int(target)})
        fmts[fid] = spec
    for fid in retired:
        spec = dict((extra_formats or {}).get(fid) or _SPECS.get(fid) or {})
        spec.update({"state": "retired", "target": 0,
                     "retired_on": "2999-01-01",
                     "retired_because": "retired by a test fixture",
                     "chatgpt_roles": ["none"]})
        fmts[fid] = spec

    reg_obj = {
        "schema_version": reg.SCHEMA_VERSION,
        "revision": revision,
        "production_date": {"timezone": "America/Chicago",
                            "policy": "utc_calendar_day",
                            "format": "YYYYMMDD"},
        "defaults": {"response_schema": "chatgpt-exchange-response/v1",
                     "failure_policy": {"on_missing_registry": "fail_closed"}},
        "channels": {
            "trending": {
                "id": "trending", "enabled": True,
                "display_name": "Trending (fixture)",
                "cadence": {"per_day": sum(trending.values())},
                "target_count": sum(trending.values()),
                "formats": fmts,
                "chatgpt_roles": ["media_worker", "editorial_review",
                                  "takeover_authoring"],
                "queue": None,
                "paths": {"packages": "state/trending_packages/<date>",
                          "posted_log": "state/posted_log.json",
                          "reserve_bank": "state/package_buffer",
                          "promotion_target": "state/trending_packages/<date>"},
                "doctrine": ["CLAUDE_ROUTINE_INSTRUCTIONS.md"],
                "protected_fields": ["numbers", "named_entities"],
                "allowed_editorial_mutations": ["title", "script_wording"],
            },
            "explainer": {
                "id": "explainer", "enabled": True,
                "display_name": "Explainer (fixture)",
                "cadence": {"per_day": 1}, "target_count": 1,
                "formats": {"data_story": {
                    "state": "active", "target": 1,
                    "renderer": "make_explainer_stacked.py",
                    "detect": {"field": "series", "present": True},
                    "media": {"shots": False},
                    "chatgpt_roles": ["editorial_review"]}},
                "chatgpt_roles": ["editorial_review"],
                "chatgpt_job": "rewrite_words",
                "response_key": "authored_explainer",
                "queue": {"config": "data_learning/niche.config.json",
                          "posted_log": "state/explainer_posted_log.json",
                          "minimum_unposted": 3},
                "paths": {"config": "data_learning/niche.config.json",
                          "posted_log": "state/explainer_posted_log.json"},
                "doctrine": ["docs/DIRECTOR.md"],
                "protected_fields": ["numbers"],
                "allowed_editorial_mutations": ["title"],
            },
            "curiosity": {
                "id": "curiosity", "enabled": True,
                "display_name": "Curiosity (fixture)",
                "cadence": {"per_day": 1}, "target_count": 1,
                "formats": {"long_form": {
                    "state": "active", "target": 1,
                    "renderer": "data_learning/longform_render.py",
                    "detect": {"field": "segments", "present": True},
                    "media": {"shots": False},
                    "chatgpt_roles": ["queue_stocking"]}},
                "chatgpt_roles": ["queue_stocking"],
                "chatgpt_job": "stock_queue",
                "response_key": "authored_curiosity",
                "queue": {"config": "data_learning/curiosity.config.json",
                          "posted_log": "state/curiosity_posted_log.json",
                          "minimum_unposted": 3},
                "paths": {"config": "data_learning/curiosity.config.json",
                          "posted_log": "state/curiosity_posted_log.json"},
                "doctrine": ["data_learning/CURIOSITY_BRAIN.md"],
                "protected_fields": [], "allowed_editorial_mutations": [],
            },
        },
    }
    if channels:
        reg_obj["channels"].update(channels)
    problems = reg.validate(reg_obj)
    if problems:
        raise ValueError(f"fixture registry is invalid: {problems}")
    return reg_obj


@contextlib.contextmanager
def registry(trending=None, **kw):
    """Run a block against a temporary registry. Restores the env after."""
    obj = kw.pop("registry_object", None) or build(trending, **kw)
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    try:
        json.dump(obj, tmp, indent=2)
        tmp.close()
        saved = os.environ.get(reg.PATH_ENV)
        os.environ[reg.PATH_ENV] = tmp.name
        reg._CACHE.clear()
        try:
            yield obj
        finally:
            if saved is None:
                os.environ.pop(reg.PATH_ENV, None)
            else:
                os.environ[reg.PATH_ENV] = saved
            reg._CACHE.clear()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


@contextlib.contextmanager
def broken_registry(content: str | None = None):
    """A missing or corrupt registry — for proving we fail honestly."""
    saved = os.environ.get(reg.PATH_ENV)
    reg._CACHE.clear()
    if content is None:
        os.environ[reg.PATH_ENV] = "/nonexistent/channel_registry.json"
        tmp = None
    else:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write(content)
        tmp.close()
        os.environ[reg.PATH_ENV] = tmp.name
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop(reg.PATH_ENV, None)
        else:
            os.environ[reg.PATH_ENV] = saved
        reg._CACHE.clear()
        if tmp:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


#: The mix the pre-registry tests were written against. Using this rather
#: than repeating the literal keeps those tests about MECHANISM.
LEGACY_MIX = {"reddit_story": 2, "text_card": 2, "graph_race": 2}
