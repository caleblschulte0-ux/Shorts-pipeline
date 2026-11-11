"""What Baller Bro may post: American sports plus soccer, spoken in English,
and never a cut too short to hold a moment. No model is needed for any of it.

Operator, 2026-11-11, after a week the main brain was out of quota and the
fallbacks ran the channel: *"no more videos that aren't English, and no more
weird-ass sports ... No sports from other countries, besides soccer"*, and
*"some clips were like 2 seconds long ... at some point, I'm going to have
this run on a local model. So it needs to be able to handle all this
shit."* That week posted cricket, a Turkish second-division pitch invasion,
an Argentine crowd, Spanish press conferences and a three-second Tomlin
quote, every one passed by a fallback judge.

So these checks are CODE, not a judge: a keyword scope on the post's
subreddit and title, a spoken-language check that runs Whisper's own
language detector locally (with a function-word count when Whisper is not
installed), and a length floor. The policy (sources, language, the floor)
is the registry's `scope` under trending's `sports_moment`.

    from shared import sports_scope
    sports_scope.out_of_scope("sports", "Lightest sumo wrestler debuts")
    -> "not an American sport: sumo"
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

CHANNEL = "trending"
FORMAT = "sports_moment"

#: Used only if the registry has no `scope` (it fails strict, never open).
DEFAULT = {"language": "en", "min_cut_s": 15,
           "sources": ["nfl", "nba", "baseball", "hockey",
                       "CollegeBasketball", "CFB", "MMA", "soccer", "sports"],
           "foreign_ok": ["soccer"]}

#: Subreddits that are ONE American league or American college sport: a
#: post there is in scope unless its title names a foreign sport.
AMERICAN_SUBS = {"nfl", "nba", "collegebasketball", "cfb", "wnba",
                 "baseball", "mlb", "hockey", "nhl", "mma", "ufc"}
SOCCER_SUBS = {"soccer", "premierleague", "mls"}

#: Sports and competitions from other countries. Soccer competitions are
#: deliberately absent: soccer from anywhere is allowed (in English).
FOREIGN = [
    "cricket", "wicket", "test match", "the ashes", "ipl", "bbl", "t20",
    "odi", "sumo", "rugby", "six nations", "super rugby", "afl", "aussie rules",
    "nrl", "state of origin", "kabaddi", "hurling", "gaelic", "camogie",
    "handball", "netball", "snooker", "darts", "badminton", "table tennis",
    "ping pong", "formula 1", "formula one", "f1", "motogp", "tour de france",
    "giro", "khl", "shl", "liiga", "iihf", "npb", "kbo", "cpbl", "nippon",
    "japan series", "koshien", "biathlon", "ski jump", "bandy", "pelota",
    "jai alai", "sepak takraw", "muay thai", "kickboxing", "bundesliga handball",
]

#: What makes an r/sports post American: a league, an event, a college
#: sport, or a team nickname from the five big leagues.
LEAGUES = [
    "nfl", "nba", "mlb", "nhl", "wnba", "ncaa", "ufc", "pga", "lpga",
    "nascar", "indycar", "mls", "xfl", "ufl", "super bowl", "world series",
    "stanley cup", "march madness", "final four", "heisman", "pro bowl",
    "college football", "college basketball", "college baseball",
    "big ten", "big 12", "sec", "acc", "little league", "high school",
    "usmnt", "uswnt", "team usa", "usa basketball", "touchdown",
    "quarterback", "home run", "slam dunk", "buzzer beater", "hail mary",
    "field goal", "walk-off", "walk off", "grand slam",
]
TEAMS = [
    # NFL
    "cardinals", "falcons", "ravens", "bills", "panthers", "bears",
    "bengals", "browns", "cowboys", "broncos", "lions", "packers", "texans",
    "colts", "jaguars", "chiefs", "raiders", "chargers", "rams", "dolphins",
    "vikings", "patriots", "saints", "giants", "jets", "eagles", "steelers",
    "49ers", "niners", "seahawks", "buccaneers", "bucs", "titans",
    "commanders",
    # NBA
    "hawks", "celtics", "nets", "hornets", "bulls", "cavaliers", "cavs",
    "mavericks", "mavs", "nuggets", "pistons", "warriors", "rockets",
    "pacers", "clippers", "lakers", "grizzlies", "bucks", "timberwolves",
    "pelicans", "knicks", "thunder", "76ers", "sixers", "suns",
    "trail blazers", "blazers", "spurs", "raptors", "wizards",
    # MLB
    "diamondbacks", "braves", "orioles", "red sox", "cubs", "white sox",
    "guardians", "rockies", "tigers", "astros", "royals", "angels",
    "dodgers", "marlins", "brewers", "twins", "mets", "yankees",
    "athletics", "phillies", "pirates", "padres", "mariners", "rays",
    "rangers", "blue jays", "nationals",
    # NHL
    "bruins", "sabres", "flames", "hurricanes", "blackhawks", "avalanche",
    "blue jackets", "red wings", "oilers", "canadiens", "predators",
    "devils", "islanders", "senators", "flyers", "penguins", "sharks",
    "kraken", "lightning", "maple leafs", "canucks", "golden knights",
    "capitals", "mammoth",
]
#: Soccer words that let an r/sports post through as soccer.
SOCCER = ["soccer", "premier league", "champions league", "world cup",
          "fa cup", "la liga", "serie a", "bundesliga", "ligue 1", "mls",
          "usmnt", "uswnt", "penalty kick", "free kick", "goalkeeper",
          "manchester united", "man united", "man city", "arsenal",
          "chelsea", "liverpool", "tottenham", "real madrid", "barcelona",
          "messi", "ronaldo", "inter miami"]


def _rx(words: list[str]) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])(" + "|".join(
        re.escape(w) for w in sorted(words, key=len, reverse=True))
        + r")(?![a-z0-9])", re.I)


_FOREIGN, _AMERICAN, _SOCCER = _rx(FOREIGN), _rx(LEAGUES + TEAMS), _rx(SOCCER)


def policy(reg=None) -> dict:
    """The registry's scope for Baller Bro, or the strict default."""
    try:
        from shared import channel_registry
        got = channel_registry.format_spec(CHANNEL, FORMAT, reg).get("scope")
    except Exception:  # noqa: BLE001
        got = None
    return dict(DEFAULT, **(got or {}))


def out_of_scope(sub: str, title: str, reg=None) -> str:
    """Why a post is not Baller Bro's kind of sport, or ''."""
    pol = policy(reg)
    s = str(sub or "").strip().lower()
    t = str(title or "")
    if s not in {x.lower() for x in pol["sources"]}:
        return f"r/{sub} is not one of the channel's sources"
    hit = _FOREIGN.search(t)
    if hit:
        return f"not an American sport: {hit.group(1).lower()}"
    if s in AMERICAN_SUBS:
        return ""
    soccer_ok = "soccer" in [x.lower() for x in pol.get("foreign_ok") or []]
    if s in SOCCER_SUBS:
        return "" if soccer_ok else "soccer is not in scope"
    # a catch-all sub: the title must name an American sport or soccer
    if _AMERICAN.search(t) or (soccer_ok and _SOCCER.search(t)):
        return ""
    return "the title names no American league, team or event"


# --- spoken language -------------------------------------------------------

#: Below this many transcribed words a clip is crowd noise or a celebration,
#: and there is no language to hear.
MIN_WORDS = 8
#: Whisper's English probability, averaged over the clip's windows, that
#: counts as English.
EN_MIN = 0.5
#: Below this it is not English whatever the words say. Between EN_GREY and
#: EN_MIN a short clip is a coin toss for the detector (the 2026-11-11 audit:
#: an English LeBron clip of 12 words scored 0.49), so the transcript's own
#: function words decide.
EN_GREY = 0.3
#: In the grey zone, the share of English function words that counts.
EN_WORDS_MIN = 0.25

_EN = set("the a an and but or so to of in on at for with is are was were "
          "it this that i you he she we they my your his her our their me "
          "him us them be been have has had do did not no what when why how "
          "just like gonna got get know think going yeah".split())
_OTHER = set("que de la el los las por porque pero y es con para una un "
             "os nos muy más mas está esta eso esto aquí aqui también "
             "não você voce isso uma com ele ela são sao "
             "le les est et pas pour une des du je tu nous vous c'est "
             "bir bu ve için icin çok cok ben sen da ama "
             "der die das und nicht ich ist ein eine mit auf "
             "di che il non per sono ma anche".split())


def _function_words(words: list[dict]) -> tuple[float, float]:
    toks = [re.sub(r"[^\w']", "", str(w.get("w", ""))).lower()
            for w in words or []]
    toks = [t for t in toks if t]
    if not toks:
        return 0.0, 0.0
    return (sum(t in _EN for t in toks) / len(toks),
            sum(t in _OTHER for t in toks) / len(toks))


@lru_cache(maxsize=1)
def _tiny():
    import whisper  # noqa: PLC0415 — optional; the word count stands in
    return whisper.load_model("tiny")


def english_probability(video: Path, words: list[dict]) -> float | None:
    """Whisper's own language detector, run locally on up to three 30s
    windows where the transcript has speech; None when Whisper is absent.
    The transcript itself cannot say: it is decoded with language="en",
    which turns Spanish into English words."""
    try:
        import whisper  # noqa: PLC0415
        model = _tiny()
        audio = whisper.load_audio(str(video))
    except Exception:  # noqa: BLE001
        return None
    starts = sorted({max(0.0, float(words[i]["s"]) - 0.5)
                     for i in (0, len(words) // 2, max(0, len(words) - 12))})
    got = []
    for s in starts:
        seg = audio[int(s * 16000): int((s + 30) * 16000)]
        if len(seg) < 16000:
            continue
        mel = whisper.log_mel_spectrogram(
            whisper.pad_or_trim(seg), n_mels=model.dims.n_mels
        ).to(model.device)
        _, probs = model.detect_language(mel)
        got.append(float(probs.get("en", 0.0)))
    return sum(got) / len(got) if got else None


def not_english(video: Path, words: list[dict]) -> str:
    """Why a clip's speech is not English, or ''. A clip with too few
    words to hear (a crowd, a celebration) passes."""
    if len(words or []) < MIN_WORDS:
        return ""
    p = english_probability(video, words)
    en, other = _function_words(words)
    if p is not None:
        if p >= EN_MIN:
            return ""
        if p >= EN_GREY and en >= EN_WORDS_MIN and en > other:
            return ""
        return f"not English (English p={p:.2f}, {en:.0%} English words)"
    if other >= 0.12 and other > en:
        return (f"not English ({other:.0%} of its words are Spanish, "
                f"Portuguese, French, Turkish, German or Italian)")
    return ""


_TEAM = _rx(TEAMS)


def invented(title: str, *sources: str) -> str:
    """A team our title names that neither the Reddit post nor
    what is said in the clip names, or '' (2026-11-07: a fallback author
    called the Minnesota GOPHERS' field goals "Minnesota Vikings")."""
    known = " ".join(str(x or "") for x in sources).lower()
    for m in _TEAM.finditer(str(title or "")):
        name = m.group(1).lower()
        if not re.search(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])",
                         known):
            return f"the title names {m.group(1)!r}, which the post never does"
    return ""


def too_short(seconds: float, reg=None) -> str:
    """Why a cut is too short to post, or ''."""
    floor = float(policy(reg).get("min_cut_s") or 0)
    if seconds and seconds < floor - 0.5:
        return f"too short: the cut runs {seconds:.1f}s (< {floor:.0f}s)"
    return ""
