"""Operator, 2026-10-09, after backtest 17:

  "your missing what makes a story it's not a collection of clips or like
  4 moments in a stream played in a row"

and, of xQc talking about a rug pull:

  "put a picture of the stock he is talking about as a layover for a few
  seconds so they can get it. Internalize what [we're] going for there"

A story is a CHAIN: every beat follows from the one before (so) or turns
against it (but); a beat that only joins by "and then" is refused. And
when a clip or a beat talks about a thing a stranger cannot see, its
picture (a price chart for a coin or a stock) is cut in at that second,
only when the match is exact.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from unittest import mock

import io
import tempfile
import unittest
from pathlib import Path

from third_capture import show_it
from third_capture import story_director as sd

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


def _plan(links):
    roles = ["setup"] + ["escalation"] * (len(links) - 1) + ["payoff"]
    beats = [{"source_id": s, "start": 0, "end": 8, "role": r,
              "purpose": "moves it on", "link": ln}
             for s, r, ln in zip("abc", roles, ["start"] + links)]
    return {"is_story": True, "premise": "p", "central_question": "q?",
            "structure": "chronological", "structure_reason": "r",
            "title": "t", "hook_overlay": "xQc hypes a coin",
            "target_duration": 30, "beats": beats}


DUR = {"a": 20.0, "b": 20.0, "c": 20.0}


# ------------------------------------------------------------ the chain
def test_so_and_but_make_a_story():
    rs = []
    edl = sd.validate_edl(_plan(["so", "but"]), DUR, reasons=rs)
    assert edl, rs
    assert [b["link"] for b in edl["beats"]] == ["start", "so", "but"]


def test_and_then_is_a_pile_not_a_story():
    for bad in ("and then", "", "then", None):
        rs = []
        assert sd.validate_edl(_plan(["so", bad]), DUR, reasons=rs) is None
        assert "not so/but" in "; ".join(rs)


def test_every_judge_is_told_the_chain():
    for prompt in (sd._PLAN_SYSTEM, sd._SCOUT_SYSTEM, sd._REVIEW_SYSTEM,
                   sd._REVISE_SYSTEM):
        assert "and then" in prompt.lower(), prompt[:60]


def test_a_beats_picture_is_kept_only_inside_the_beat():
    p = _plan(["so", "but"])
    p["beats"][1]["show"] = {"thing": "Hawk Tuah", "kind": "coin", "at": 4}
    p["beats"][2]["show"] = {"thing": "GameStop", "kind": "stock", "at": 15}
    edl = sd.validate_edl(p, DUR)
    assert edl["beats"][1]["show"] == {"thing": "Hawk Tuah", "kind": "coin",
                                       "at": 4.0}
    assert "show" not in edl["beats"][2]       # named after the beat ends


# ------------------------------------------------------------- the plan
def test_the_picture_lands_on_the_cut_not_the_clip():
    p = show_it.plan([{"thing": "Elden Ring", "kind": "thing", "at": 12}],
                     20.0, offset=5.0)
    assert p == [{"thing": "Elden Ring", "kind": "thing", "at": 7.0,
                  "secs": show_it.SHOW_S, "look": ""}]
    # named before the cut, or too late to stay up: not shown
    assert show_it.plan([{"thing": "X", "at": 3}], 20.0, offset=5.0) == []
    assert show_it.plan([{"thing": "X", "at": 19.5}], 20.0) == []


def test_at_most_two_and_never_on_top_of_each_other():
    items = [{"thing": t, "at": a} for t, a in
             (("A", 1), ("B", 2), ("C", 6), ("D", 10))]
    got = show_it.plan(items, 30.0)
    assert [g["thing"] for g in got] == ["A", "C"]


def test_the_author_names_what_to_show():
    from third_capture import author
    out = author._postprocess(
        {"title": "xQc loses it all on a meme coin", "hook": "xQc hypes a coin",
         "hashtags": ["xqc"], "series": "fail",
         "edit": {"show": [{"thing": "$HAWK", "kind": "coin", "at": 6.2},
                           {"thing": "", "kind": "thing", "at": 2},
                           {"thing": "Lambo", "kind": "car?", "at": 9}]}},
        "xqc", "x", clip_dur=20.0)
    assert out["edit"]["show"] == [
        {"thing": "$HAWK", "kind": "coin", "at": 6.2},
        {"thing": "Lambo", "kind": "thing", "at": 9.0}]
    assert '"show"' in author.SYSTEM and '"look"' in author.SYSTEM


# ------------------------------------- the shared finder: look everywhere
# Operator, same night: "there needs to be a lot of capabilities that
# aren't just on Wikipedia ... we 100% can use copyrighted images ...
# make sure you're adding any capabilities to the shared area".
from funnel import find_image  # noqa: E402


def _fake_json(table):
    def f(url):
        for k, v in table.items():
            if k in url:
                return v
        raise OSError(url)
    return f


def _png(tmp, name, size=(400, 300), color=(200, 30, 30)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def test_the_finder_is_shared_and_searches_every_source():
    import inspect
    src = inspect.getsource(find_image)
    assert "media_funnel.search" in src          # news/Brave/DDG/Reddit/...
    assert "judge_panels" in src                 # the brain checks it
    assert "find_image.find" in inspect.getsource(show_it.fetch)
    # third_capture keeps no private copy of a search or a data source
    assert "coingecko" not in inspect.getsource(show_it).lower()


def test_a_coin_matches_only_its_own_name_or_ticker():
    table = {"/search?query=": {"coins": [
                 {"id": "x", "name": "Hawk Tuah Inu", "symbol": "HTI",
                  "large": None}]},
             "dexscreener": {"pairs": []}}
    with mock.patch.object(find_image, "_json",
                           side_effect=_fake_json(table)):
        assert find_image.coin("Hawk Tuah") is None
    table["/search?query="]["coins"].append(
        {"id": "hawk", "name": "Hawk Tuah", "symbol": "HAWK", "large": None})
    table["market_chart"] = {"prices": [[1e12, 1.0], [1.1e12, 9.0],
                                        [1.2e12, 0.4]]}
    with mock.patch.object(find_image, "_json",
                           side_effect=_fake_json(table)):
        got = find_image.coin("$HAWK coin")
    assert got["name"] == "Hawk Tuah" and len(got["prices"]) == 3


def test_wikipedia_must_be_the_thing_and_never_a_disambiguation():
    def page(title, props=None):
        return {"query": {"pages": {"1": {
            "title": title, "pageprops": props or {},
            "thumbnail": {"source": "https://x/y.jpg"}}}}}
    with mock.patch.object(find_image, "_json",
                           return_value=page("Elden Ring")):
        assert find_image.wiki("Elden Ring")["name"] == "Elden Ring"
    with mock.patch.object(find_image, "_json",
                           return_value=page("Ring (jewellery)")):
        assert find_image.wiki("Elden Ring") is None
    with mock.patch.object(find_image, "_json", return_value=page(
            "Mercury", {"disambiguation": ""})):
        assert find_image.wiki("Mercury") is None


def _finder(tmp, *, verdicts, urls, wiki_hit=None):
    imgs = {u: _png(tmp, u) for u in urls + (
        [wiki_hit["url"]] if wiki_hit else [])}
    return [mock.patch.object(find_image, "wiki", return_value=wiki_hit),
            mock.patch.object(find_image, "search_urls", return_value=[
                {"url": u, "source": "ddg", "title": u} for u in urls]),
            mock.patch.object(find_image, "_bytes",
                              side_effect=lambda u: imgs.get(u)),
            mock.patch.object(find_image, "judge", return_value=verdicts)]


def _run(patches, *a, **k):
    for p in patches:
        p.start()
    try:
        return find_image.find(*a, **k)
    finally:
        for p in patches:
            p.stop()


def test_the_first_picture_the_brain_says_shows_it_wins(tmp_path):
    got = _run(_finder(tmp_path, urls=["https://a/1", "https://b/2"],
                       wiki_hit={"name": "HAWK", "url": "https://w/0"},
                       verdicts={0: {"depicts": False}, 1: {"depicts": False},
                                 2: {"depicts": True}}),
               "HAWK coin", "HAWK coin chart after the rug pull",
               kind="coin", work=tmp_path)
    assert got["url"] == "https://b/2" and got["via"] == "judged"
    assert Path(got["path"]).exists()


def test_with_no_brain_only_the_exact_wikipedia_picture_is_used(tmp_path):
    got = _run(_finder(tmp_path, urls=["https://a/1"], verdicts=None,
                       wiki_hit={"name": "Elden Ring", "url": "https://w/0"}),
               "Elden Ring", work=tmp_path)
    assert got["url"] == "https://w/0" and got["via"] == "exact"
    assert _run(_finder(tmp_path, urls=["https://a/1"], verdicts=None),
                "Elden Ring", work=tmp_path) is None


def test_a_coin_nothing_showed_is_drawn_from_its_prices(tmp_path):
    info = {"name": "Hawk Tuah", "symbol": "HAWK", "logo": None,
            "prices": [(0, 1.0), (1, 9.0), (2, 0.2)]}
    with mock.patch.object(find_image, "coin", return_value=info):
        got = _run(_finder(tmp_path, urls=["https://a/1"],
                           verdicts={0: {"depicts": False}}),
                   "HAWK", "HAWK chart after the rug pull", kind="coin",
                   work=tmp_path)
    assert got == {"chart": info, "source": "coin_prices"}


def test_a_thumbnail_is_not_a_pop_up(tmp_path):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (120, 90)).save(buf, "PNG")
    with mock.patch.object(find_image, "_bytes",
                           return_value=buf.getvalue()):
        assert find_image._download("https://x", tmp_path / "t.png") is None


def test_nothing_found_shows_nothing(tmp_path):
    with mock.patch.object(find_image, "find", return_value=None):
        assert show_it.fetch({"thing": "Hawk Tuah", "kind": "coin"},
                             tmp_path) is None
        assert show_it.ready([{"thing": "X", "kind": "thing", "at": 1,
                               "secs": 2}], tmp_path) == []


def test_the_look_travels_from_the_writer_to_the_finder(tmp_path):
    seen = {}

    def find(thing, look, **k):
        seen["look"] = look
        return None
    plan = show_it.plan(show_it.parse([{
        "thing": "HAWK", "kind": "coin", "at": 4,
        "look": "HAWK coin chart after the rug pull"}]), 20.0)
    with mock.patch.object(find_image, "find", side_effect=find):
        show_it.ready(plan, tmp_path)
    assert seen["look"] == "HAWK coin chart after the rug pull"


def test_a_rug_pull_reads_off_its_peak(tmp_path):
    from PIL import Image
    info = {"name": "Hawk Tuah", "symbol": "HAWK", "logo": None,
            "prices": [(i, p) for i, p in enumerate(
                [0.01, 0.02, 0.2, 0.9, 0.05, 0.03])]}
    png = show_it.chart_card(info, tmp_path / "c.png")
    im = Image.open(png).convert("RGB")
    assert im.width == show_it.CARD_W
    # the line is red: a crash, not "+200% since the first day"
    px = [im.getpixel((x, y)) for x in range(0, im.width, 4)
          for y in range(200, im.height - 40, 4)]
    reds = sum(1 for r, g, b in px if r > 200 and g < 90)
    greens = sum(1 for r, g, b in px if g > 180 and r < 90)
    assert reds > 50 and greens == 0


# --------------------------------------------------------- on the video
def test_the_picture_is_on_screen_for_its_seconds_only(tmp_path):
    if not HAVE_FFMPEG:
        raise unittest.SkipTest("ffmpeg unavailable")
    import numpy as np
    from PIL import Image
    pic = tmp_path / "p.png"
    Image.new("RGBA", (show_it.CARD_W, 500), (255, 0, 0, 255)).save(pic)
    item = {"at": 2.0, "secs": 2.0, "png": pic}
    src = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=black:s=1080x1920:r=30:d=6", "-c:v", "libx264",
                    str(src)], check=True)
    out = tmp_path / "o.mp4"
    chain = (f"[0:v]null[v0];{show_it.overlay('v0', 1, item, 'sh')};"
             "[sh]null[vout]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-i",
                    str(pic), "-filter_complex", chain, "-map", "[vout]",
                    "-t", "6", "-c:v", "libx264", str(out)], check=True)

    def red(t):
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(out),
             "-frames:v", "1", "-vf", "scale=108:192", "-pix_fmt", "rgb24",
             "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
        a = np.frombuffer(raw, np.uint8).reshape(192, 108, 3)
        return float(a[..., 0].mean())
    assert red(1.0) < 5
    assert red(3.0) > 20
    assert red(5.0) < 5


def test_the_clip_and_the_story_both_render_it():
    import inspect
    from third_capture import clip_edit, story
    assert "show_it.overlay" in inspect.getsource(clip_edit.edit)
    assert "shows=shows" in inspect.getsource(story.render_story)
    assert "movie=" in inspect.getsource(story._extract_segment)


def test_sex_sells_with_dignity():
    """Operator, 2026-10-09: "we have the green light to goonbait not to
    much let's keep our dignity but sex sells". The picker and the writer
    both lean in, and both are told the line."""
    from third_capture import author
    for prompt in (author.SYSTEM, author._RANK_SYSTEM,
                   author._CONTENT_SYSTEM):
        assert "SEX SELLS" in prompt
        assert "under 18" in prompt and "age-restrict" in prompt



# ------------------------------------------------- it has to be FUN
# Operator, 2026-10-10, of backtest 18: "None of them are entertaining is
# the issue."
def _critic(out):
    with mock.patch.object(sd, "_brain", return_value=out):
        return sd.review_rough_cut(sd.validate_edl(_plan(["so", "but"]), DUR),
                                   "", None, 30.0)


def test_a_coherent_cut_nobody_enjoys_cannot_publish_or_near_miss():
    base = {"publish": True, "story_score": 84, "payoff_at": 20.0,
            "stranger_summary": "He explains a level, then gets it."}
    r = _critic(base)
    assert not r["publish"] and r["story_score"] <= sd.NOT_FUN_MAX
    assert r["problems"][-1]["type"] == "not_entertaining"
    r = _critic({**base, "entertaining_at": 18.0,
                 "entertaining_why": "his friend faceplants into the cake"})
    assert r["publish"] and r["story_score"] == 84


def test_every_story_judge_is_told_it_must_entertain():
    for prompt in (sd._PLAN_SYSTEM, sd._REVIEW_SYSTEM):
        assert "ENTERTAINING" in prompt
    assert "entertaining_at" in sd._REVIEW_SYSTEM


def test_the_internet_picks_go_first_and_the_director_hears_why():
    from third_capture import storyline
    pool = [{"url": "https://clips.twitch.tv/Big", "views": 90000,
             "video_id": "1", "vod_offset": 100, "channel": "a"},
            {"url": "https://clips.twitch.tv/Fun", "views": 900,
             "video_id": "2", "vod_offset": 100, "channel": "b",
             "internet": {"upvotes": 4200, "post_title": "B falls off "
                          "the stage mid-speech"}}]
    m = storyline.find_moments(pool)
    assert m[0]["clips"][0]["source_url"].endswith("Fun")
    assert m[0]["clips"][0]["internet"]["upvotes"] == 4200
    rep = {"source_id": "s", "channel": "b", "duration_s": 30, "summary": "",
           "internet": {"upvotes": 4200,
                        "post_title": "B falls off the stage mid-speech"}}
    assert "falls off the stage" in sd._fmt_reports([rep])


def test_livestreamfail_yields_twitch_clips_best_first():
    from funnel import hot_clips
    listing = {"data": {"children": [
        {"data": {"url": "https://www.twitch.tv/xqc/clip/SlugOne-abc",
                  "title": "xQc loses it", "ups": 900, "permalink": "/r/x"}},
        {"data": {"url": "https://clips.twitch.tv/SlugTwo-def",
                  "title": "Kai's mom walks in", "ups": 5000}},
        {"data": {"url": "https://youtube.com/watch?v=1", "ups": 9999}},
        {"data": {"url": "https://clips.twitch.tv/Nsfw-x", "ups": 7000,
                  "over_18": True}}]}}
    with mock.patch.object(hot_clips, "_listing", return_value=listing):
        got = hot_clips.livestreamfail()
    assert [g["slug"] for g in got] == ["SlugTwo-def", "SlugOne-abc"]
    assert got[0]["post_title"] == "Kai's mom walks in"
    with mock.patch.object(hot_clips, "_listing", return_value=None):
        assert hot_clips.livestreamfail() == []



# ---- THE OTHER SIDE (operator, 2026-10-10, of the Kai Cenat / Reggie
# saga: "take whoever made those allegations originally, that stream, take
# a clip from there, and then go to Kai's stream ... that's a story")

def test_the_other_side_is_found_on_any_platform_in_the_order_it_was_said():
    from funnel import hot_clips
    found = {"data": {"children": [
        {"data": {"url": "https://www.youtube.com/watch?v=part2",
                  "title": "Reggie releases part 2", "ups": 3000,
                  "created_utc": 300, "permalink": "/r/LSF/b"}},
        {"data": {"url": "https://clips.twitch.tv/KaiSaysLie-x",
                  "title": "Kai Cenat responds to Reggie", "ups": 9000,
                  "created_utc": 200}},
        {"data": {"url": "https://x.com/reggie/status/1",
                  "title": "Reggie's original allegations", "ups": 5000,
                  "created_utc": 100}},
        {"data": {"url": "https://v.redd.it/abc", "permalink": "/r/LSF/c",
                  "title": "Kai: part two had no evidence", "ups": 800,
                  "created_utc": 400}},
        {"data": {"url": "https://www.dexerto.com/article", "ups": 99999,
                  "created_utc": 50, "title": "an article"}},
        {"data": {"url": "https://streamable.com/n", "over_18": True,
                  "created_utc": 60}}]}}
    with mock.patch.object(hot_clips, "_search",
                           return_value=found) as srch:
        got = hot_clips.about("Kai Cenat")
    assert srch.call_args[0][0] == "Kai Cenat"
    assert [g["platform"] for g in got] == ["x", "twitch", "youtube",
                                            "reddit"]
    assert got[1]["slug"] == "KaiSaysLie-x"
    assert got[3]["url"] == "https://www.reddit.com/r/LSF/c"
    with mock.patch.object(hot_clips, "_search", return_value=None):
        assert hot_clips.about("Kai Cenat") == []


def test_the_scout_reads_the_other_side_even_with_no_twitch_views():
    from third_capture import storyline
    pool = [{"url": f"https://clips.twitch.tv/k{i}", "views": 50000 - i,
             "channel": "kaicenat", "title": f"kai clip {i}", "age_h": 5}
            for i in range(5)]
    pool.append({"url": "https://www.youtube.com/watch?v=part2",
                 "platform": "youtube", "channel": "", "views": 0,
                 "title": "Reggie releases part 2", "age_h": 30,
                 "internet": {"upvotes": 3000,
                              "post_title": "Reggie releases part 2"}})
    lines, ids = storyline.build_catalogue(storyline.from_discovery(pool),
                                           max_fresh=3)
    yt = [ln for ln in lines if "Reggie releases part 2" in ln]
    assert yt, lines
    assert "r/LSF" in yt[0] and " | ? | " in yt[0]
    clip = [c for c in ids.values() if "youtube" in c["source_url"]][0]
    assert clip["platform"] == "youtube"


def test_every_judge_is_told_a_feud_is_both_sides_and_attributed():
    assert "r/LSF" in sd._SCOUT_SYSTEM and "FEUD" in sd._SCOUT_SYSTEM
    assert "BOTH CHANNELS" in sd._PLAN_SYSTEM
    assert "ATTRIBUTED" in sd._PLAN_SYSTEM


def test_an_off_twitch_source_is_not_given_a_streamer_it_does_not_have():
    rep = {"source_id": "s", "channel": "", "platform": "youtube",
           "duration_s": 40, "summary": ""}
    txt = sd._fmt_reports([rep])
    assert "streamer=unknown" in txt and "youtube" in txt


def test_a_story_source_longer_than_a_clip_is_refused_before_download(
        tmp_path):
    from third_capture import clip_edit
    with mock.patch.object(clip_edit, "_ytdlp") as y:
        try:
            clip_edit.download("https://youtube.com/watch?v=long",
                               tmp_path, max_s=600)
            raise AssertionError("a filtered video must not pass")
        except ValueError:
            pass
    args = y.call_args[0][0]
    assert args[args.index("--match-filter") + 1] == "duration<=?600"


def test_the_story_pool_searches_for_the_other_side():
    import ast
    src = (Path(__file__).resolve().parents[1] / "scripts"
           / "run_third.py").read_text()
    calls = {f"{n.func.value.id}.{n.func.attr}"
             for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and isinstance(n.func.value, ast.Name)}
    assert "hot_clips.about" in calls



def test_reddit_refusing_the_api_still_reaches_the_posts():
    # backtest 19: both listings HTTPError from the runner, 0 clips
    from funnel import hot_clips
    hot_clips._DEAD.clear()
    atom = ("<feed><entry><title>Reggie releases part 2 &amp; more</title>"
            '<link href="https://www.reddit.com/r/LivestreamFail/comments/'
            'x/reggie/"/><published>2026-10-08T12:00:00+00:00</published>'
            '<content type="html">&lt;a href=&quot;https://www.youtube.com/'
            'watch?v=p2&quot;&gt;[link]&lt;/a&gt;</content></entry></feed>')
    with mock.patch.object(hot_clips, "_get", return_value=None), \
            mock.patch.object(hot_clips, "_pullpush", return_value=None), \
            mock.patch.object(hot_clips, "_fetch",
                              return_value=atom.encode()):
        got = hot_clips.about("Kai Cenat")
    assert got and got[0]["url"] == "https://www.youtube.com/watch?v=p2"
    assert got[0]["post_title"] == "Reggie releases part 2 & more"
    assert got[0]["permalink"].endswith("/comments/x/reggie/")
    assert got[0]["created"] > 0
    hot_clips._DEAD.clear()
    pp = {"data": {"children": [{"data": {
        "url": "https://clips.twitch.tv/HotClip-1", "title": "t", "score": 70}}]}}
    with mock.patch.object(hot_clips, "_get", return_value=None), \
            mock.patch.object(hot_clips, "_pullpush", return_value=pp), \
            mock.patch.object(hot_clips, "_rss") as rss:
        got = hot_clips.livestreamfail()
    assert got[0]["slug"] == "HotClip-1" and got[0]["upvotes"] == 70
    rss.assert_not_called()
    # a route that failed is not asked again this run (seventy searches
    # against a hung host would spend the whole run)
    hot_clips._DEAD.clear()
    with mock.patch.object(hot_clips, "_get", return_value=None) as api, \
            mock.patch.object(hot_clips, "_pullpush", return_value=None), \
            mock.patch.object(hot_clips, "_rss", return_value=None):
        for name in ("a", "b", "c"):
            hot_clips.about(name)
    assert api.call_count == 1
    hot_clips._DEAD.clear()



def _rt():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_third_other_side",
        Path(__file__).resolve().parents[1] / "scripts" / "run_third.py")
    rt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rt)
    return rt


def test_the_scout_names_whose_side_is_missing():
    out = {"stories": [{"members": ["C1", "C2"], "premise": "Kai answers",
                        "why_connected": "same feud", "shape": "multi_stream",
                        "other_side": ["Reggie", "", 7, "a", "b"]}]}
    with mock.patch.object(sd, "_brain", return_value=out):
        got = sd.scout_stories(["C1 | x", "C2 | y"], {"C1", "C2"})
    assert got[0]["other_side"] == ["Reggie", "a"]
    assert "other_side" in sd._SCOUT_SYSTEM


def test_a_missing_side_is_searched_for_and_joins_the_story():
    rt = _rt()
    members = [{"source_url": "https://clips.twitch.tv/KaiLie-1",
                "channel": "kaicenat", "date": "2026-10-05"}]
    found = [{"url": "https://x.com/reggie/status/11", "platform": "x",
              "title": "Reggie's allegations", "channel": "",
              "created": 1759300000.0,
              "internet": {"upvotes": 5000, "post_title": "Reggie's"}},
             {"url": "https://clips.twitch.tv/KaiLie-1", "platform": "twitch",
              "title": "dup", "created": 1759400000.0},
             {"url": "https://www.youtube.com/watch?v=Part2xx",
              "platform": "youtube", "title": "Reggie part 2",
              "channel": "Reggie", "created": 1759500000.0}]
    from funnel import hot_clips
    with mock.patch.object(hot_clips, "other_side",
                           return_value=found) as srch:
        got = rt._other_side_clips({"other_side": ["Reggie"]}, members, {})
    assert srch.call_args[0] == ("Reggie", "Kai Cenat")
    assert [g["platform"] for g in got] == ["x", "youtube"]
    assert got[0]["date"] and got[0]["internet"]["upvotes"] == 5000
    assert got[1]["channel"] == "Reggie"


def test_a_youtube_video_or_reddit_post_keeps_its_own_identity():
    rt = _rt()
    a = rt._clip_key("https://www.youtube.com/watch?v=AAAAAA")
    b = rt._clip_key("https://www.youtube.com/watch?v=BBBBBB")
    assert a != b and a == rt._clip_key("https://youtu.be/AAAAAA?t=4")
    assert rt._clip_key("https://www.reddit.com/r/LSF/comments/k1/x/") != \
        rt._clip_key("https://www.reddit.com/r/LSF/comments/k2/x/")
    # what the posted log already holds keys exactly as before
    assert rt._clip_key("https://www.twitch.tv/a/clip/Slug-1?x") == "slug-1"


def test_the_other_side_comes_from_reddit_and_youtube_oldest_first():
    from funnel import hot_clips
    posts = [{"url": "https://x.com/r/status/1", "platform": "x",
              "slug": None, "post_title": "Reggie accuses Kai",
              "upvotes": 9, "comments": 1, "permalink": "p", "created": 200}]
    vids = [{"url": "https://www.youtube.com/watch?v=Old111",
             "platform": "youtube", "title": "Reggie responds",
             "channel": "Reggie", "created": 100}]
    with mock.patch.object(hot_clips, "about", return_value=posts) as ab, \
            mock.patch.object(hot_clips, "youtube", return_value=vids):
        got = hot_clips.other_side("Reggie", "Kai Cenat")
    assert ab.call_args[0][0] == "Reggie Kai Cenat"
    assert [g["created"] for g in got] == [100, 200]
    assert got[1]["internet"]["post_title"] == "Reggie accuses Kai"


def test_youtube_keeps_only_clip_length_videos():
    from funnel import hot_clips

    def yt(params):
        if params["_api"] == "search":
            return {"items": [
                {"id": {"videoId": "short1"}, "snippet": {
                    "title": "Reggie &amp; Kai", "channelTitle": "R",
                    "publishedAt": "2026-10-01T00:00:00Z"}},
                {"id": {"videoId": "long22"}, "snippet": {"title": "2h"}}]}
        return {"items": [{"id": "short1",
                           "contentDetails": {"duration": "PT3M5S"}},
                          {"id": "long22",
                           "contentDetails": {"duration": "PT2H"}}]}
    with mock.patch.object(hot_clips, "_yt", side_effect=yt):
        got = hot_clips.youtube("Reggie Kai Cenat")
    assert [g["url"][-6:] for g in got] == ["short1"]
    assert got[0]["title"] == "Reggie & Kai" and got[0]["created"] > 0


def test_a_rate_limited_feed_waits_and_asks_again():
    import urllib.error
    from funnel import hot_clips
    err = urllib.error.HTTPError("u", 429, "slow", {"Retry-After": "0"},
                                 None)
    feed = (b"<feed><entry><title>t</title><link href=\"https://www."
            b"reddit.com/r/x/comments/a/b/\"/></entry></feed>")
    with mock.patch.object(hot_clips, "_fetch",
                           side_effect=[err, feed]) as f:
        got = hot_clips._rss("/r/x/top.json?t=week")
    assert f.call_count == 2 and got["data"]["children"]


class Everything(unittest.TestCase):
    """CI runs `unittest discover`, which collects only TestCases; every
    function above runs here as well as under pytest."""


def _attach():
    import inspect as _i
    for name, fn in list(globals().items()):
        if not (name.startswith("test_") and callable(fn)):
            continue
        takes_tmp = "tmp_path" in _i.signature(fn).parameters

        def case(self, fn=fn, takes_tmp=takes_tmp):
            if takes_tmp:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
        setattr(Everything, name, case)


_attach()
