"""Caption grouping: ONE implementation, provably identical to the old ones.

Audit finding C. `shared/captions.py` was built for exactly this job and then
imported by nothing, while five renderers each carried a near-identical
private `_chunk_words`. That is the Ken Burns problem again — a capability
nothing calls is not a capability.

The risk in consolidating is obvious: caption timing is what every video
looks like, and a "cleanup" that silently re-cuts every line is a visual
regression nobody asked for. So the tests that matter here are the
EQUIVALENCE tests — the original implementations are reproduced verbatim
below as reference oracles, and the shared grouper must agree with them
word-for-word on generated streams.

If you change `group_words`, these tests tell you whose videos you changed.

    python -m unittest tests.test_captions -v
"""
from __future__ import annotations

import random
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from shared import captions                            # noqa: E402


@dataclass
class W:
    """Same shape as make_explainer_stacked.Word."""
    text: str
    start: float
    end: float


# --------------------------------------------------------------------------
# Reference oracle: make_reddit_story._chunk_words as it was BEFORE the
# consolidation. Copied verbatim (only the constants inlined). Do not
# "improve" this — its whole value is being the old behaviour.
# --------------------------------------------------------------------------
CAP_MAX_WORDS, CAP_MAX_CHARS = 3, 22


def reddit_chunk_words_ORIGINAL(words):
    chunks, cur = [], []
    for w in words:
        if not w.text.strip():
            continue
        cur.append(w)
        joined = " ".join(x.text.strip() for x in cur)
        ends_sentence = w.text.strip()[-1] in ".!?,"
        if len(cur) >= CAP_MAX_WORDS or len(joined) >= CAP_MAX_CHARS \
                or ends_sentence:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def reddit_via_shared(words):
    """Exactly what make_reddit_story now calls."""
    return captions.group_words(
        words, max_words=CAP_MAX_WORDS, max_chars=CAP_MAX_CHARS,
        break_on_punct=True, max_gap=float("inf"), max_span=float("inf"))


def random_stream(rng, n=60):
    vocab = ["so", "then", "she", "said", "no.", "wait", "what?", "I",
             "genuinely", "could", "not", "believe", "it,", "and", "honestly",
             "unbelievable", "", "   ", "hmm...", "yeah!"]
    out, t = [], 0.0
    for _ in range(n):
        dur = rng.uniform(0.08, 0.55)
        gap = rng.choice([0.0, 0.0, 0.0, rng.uniform(0.0, 1.4)])
        t += gap
        out.append(W(rng.choice(vocab), round(t, 3), round(t + dur, 3)))
        t += dur
    return out


class TestItIsTheSameCutAsBefore(unittest.TestCase):
    """The consolidation must not change a single caption boundary."""

    def test_identical_on_500_random_streams(self):
        rng = random.Random(20260801)
        for i in range(500):
            words = random_stream(rng)
            a = reddit_chunk_words_ORIGINAL(words)
            b = reddit_via_shared(words)
            self.assertEqual([[w.text for w in c] for c in a],
                             [[w.text for w in c] for c in b],
                             f"stream {i} groups differently — this changes "
                             f"what reddit_story videos look like")

    def test_identical_on_the_awkward_edges(self):
        cases = [
            [],
            [W("one", 0, 1)],
            [W("", 0, 1), W("  ", 1, 2)],
            [W("a.", 0, 1)],
            [W("supercalifragilistic", 0, 1), W("expialidocious", 1, 2)],
            [W("a", 0, .1), W("b", .1, .2), W("c", .2, .3), W("d", .3, .4)],
            [W("hi", 0, .1), W("", .1, .2), W("there!", .2, .3)],
            [W("x", 0, .1), W("y", 9, 9.1)],          # a huge pause
        ]
        for words in cases:
            self.assertEqual(
                [[w.text for w in c] for c in
                 reddit_chunk_words_ORIGINAL(words)],
                [[w.text for w in c] for c in reddit_via_shared(words)],
                f"differs on {[w.text for w in words]}")

    def test_the_renderer_actually_delegates(self):
        src = (ROOT / "make_reddit_story.py").read_text()
        self.assertIn("captions.group_words", src,
                      "make_reddit_story kept its private copy")

    def test_delegating_still_produces_usable_chunks(self):
        """Guard against 'identical' being satisfied by both returning []."""
        import make_reddit_story
        words = [W("so", 0, .2), W("she", .2, .4), W("said", .4, .7),
                 W("absolutely", .7, 1.2), W("not.", 1.2, 1.5)]
        chunks = make_reddit_story._chunk_words(words)
        self.assertTrue(chunks)
        self.assertTrue(all(chunks))
        self.assertEqual(sum(len(c) for c in chunks), len(words))


def explainer_group_words_ORIGINAL(words, max_chars=22, max_words=5):
    """make_explainer_stacked.group_words as it was BEFORE consolidation.
    Note the differences from reddit's: `:` and `;` also break, blank words
    are KEPT, and the char count is of the UNstripped join."""
    chunks, bucket = [], []
    for w in words:
        bucket.append(w)
        joined = " ".join(b.text for b in bucket)
        tail = w.text.rstrip()
        boundary = tail.endswith((".", ",", "!", "?", ":", ";"))
        if boundary or len(joined) >= max_chars or len(bucket) >= max_words:
            chunks.append((bucket[0].start, bucket[-1].end, joined))
            bucket = []
    if bucket:
        chunks.append((bucket[0].start, bucket[-1].end,
                       " ".join(b.text for b in bucket)))
    return chunks


class TestExplainerIsTheSameCutToo(unittest.TestCase):
    """Two renderers, two different rule sets, one grouper. This is the test
    that catches 'I made them consistent' — they are deliberately NOT."""

    def via_shared(self, words, max_chars=22, max_words=5):
        import make_explainer_stacked as mes
        return [(c.start, c.end, c.text)
                for c in mes.group_words(words, max_chars, max_words)]

    def test_identical_on_500_random_streams(self):
        rng = random.Random(19991)
        for i in range(500):
            words = random_stream(rng)
            self.assertEqual(explainer_group_words_ORIGINAL(words),
                             self.via_shared(words),
                             f"stream {i} — this changes explainer videos")

    def test_it_breaks_on_a_colon_where_reddit_does_not(self):
        ws = [W("listen:", 0, .1), W("this", .1, .2)]
        self.assertEqual(len(self.via_shared(ws)), 2)
        self.assertEqual(len(reddit_via_shared(ws)), 1,
                         "reddit_story must NOT have gained a colon break")

    def test_it_keeps_blank_words_where_reddit_drops_them(self):
        ws = [W("a", 0, .1), W("", .1, .2), W("b", .2, .3)]
        flat = sum(len(c[2].split(" ")) for c in self.via_shared(ws))
        self.assertGreaterEqual(flat, 3, "explainer's blank words vanished")
        red = [w for ln in reddit_via_shared(ws) for w in ln]
        self.assertEqual([w.text for w in red], ["a", "b"])

    def test_edges(self):
        for ws in ([], [W("solo", 0, 1)], [W("", 0, 1)],
                   [W("a:", 0, .1), W("b;", .1, .2), W("c", .2, .3)],
                   [W("x" * 40, 0, 1)]):
            self.assertEqual(explainer_group_words_ORIGINAL(ws),
                             self.via_shared(ws),
                             f"differs on {[w.text for w in ws]}")


def clip_edit_group_ORIGINAL(words, max_group=4):
    """third_capture/clip_edit.py's grouping as it was. Third word shape
    (`s`/`e`/`w`), and note `group[-1]["w"][-1:] in ".?!,"` — which is True
    for a BLANK word, because "" is a substring of everything."""
    out, group = [], []
    for w in words:
        if group and (w["s"] - group[-1]["e"] > 0.6
                      or len(group) >= max_group
                      or group[-1]["w"][-1:] in ".?!,"):
            out.append(list(group))
            group.clear()
        group.append(w)
    if group:
        out.append(list(group))
    return out


class TestClipEditIsTheSameCutToo(unittest.TestCase):
    """The third channel's renderer, third word shape, and a latent quirk
    that a refactor must preserve rather than quietly fix."""

    def via_shared(self, words, max_group=4):
        from shared import captions
        return captions.group_words(
            words, max_words=max_group, max_gap=0.6, max_span=float("inf"),
            break_on_punct=True, break_chars=".?!,", drop_empty=False,
            blank_breaks=True)

    def stream(self, rng, n=50):
        vocab = ["hey", "wait.", "what?", "no", "bro", "", "yes,", "okay!"]
        out, t = [], 0.0
        for _ in range(n):
            d = rng.uniform(.05, .4)
            t += rng.choice([0.0, 0.0, rng.uniform(0, 1.2)])
            out.append({"w": rng.choice(vocab), "s": round(t, 3),
                        "e": round(t + d, 3)})
            t += d
        return out

    def test_identical_on_500_random_streams(self):
        rng = random.Random(4242)
        for i in range(500):
            ws = self.stream(rng)
            self.assertEqual(clip_edit_group_ORIGINAL(ws),
                             self.via_shared(ws), f"stream {i}")

    def test_the_blank_word_quirk_is_preserved_not_silently_fixed(self):
        ws = [{"w": "a", "s": 0, "e": .1}, {"w": "", "s": .1, "e": .2},
              {"w": "b", "s": .2, "e": .3}]
        self.assertEqual(clip_edit_group_ORIGINAL(ws), self.via_shared(ws))
        self.assertEqual(len(self.via_shared(ws)), 2,
                         "a blank word broke a line here and still must")

    def test_other_callers_did_NOT_inherit_the_quirk(self):
        ws = [W("a", 0, .1), W("", .1, .2), W("b", .2, .3)]
        self.assertEqual(len(reddit_via_shared(ws)), 1,
                         "reddit_story must not have gained blank-breaks")

    def test_the_renderer_delegates(self):
        src = (ROOT / "third_capture" / "clip_edit.py").read_text()
        self.assertIn("captions.group_words", src)


class TestTheBreakRules(unittest.TestCase):
    """Each rule, on its own, so a future edit says which one it broke."""

    def line_texts(self, lines):
        return [[captions.word_text(w) for w in ln] for ln in lines]

    def test_max_words(self):
        ws = [W(str(i), i * .1, i * .1 + .05) for i in range(7)]
        got = captions.group_words(ws, max_words=3, max_gap=99, max_span=99)
        self.assertEqual([len(x) for x in got], [3, 3, 1])

    def test_a_pause_breaks_a_line(self):
        ws = [W("a", 0, .1), W("b", 2.0, 2.1)]
        got = captions.group_words(ws, max_gap=0.6, max_span=99)
        self.assertEqual(len(got), 2)

    def test_span_breaks_a_long_line(self):
        ws = [W("a", 0, .1), W("b", .1, .2), W("c", .2, 9.0)]
        got = captions.group_words(ws, max_words=99, max_gap=99, max_span=3.5)
        self.assertEqual(len(got), 2)

    def test_max_chars(self):
        ws = [W("aaaaaaaaaa", 0, .1), W("bbbbbbbbbb", .1, .2),
              W("c", .2, .3)]
        got = captions.group_words(ws, max_words=99, max_chars=15,
                                   max_gap=99, max_span=99)
        self.assertEqual(self.line_texts(got)[0],
                         ["aaaaaaaaaa", "bbbbbbbbbb"])

    def test_punctuation(self):
        ws = [W("stop.", 0, .1), W("go", .1, .2)]
        got = captions.group_words(ws, max_words=99, break_on_punct=True,
                                   max_gap=99, max_span=99)
        self.assertEqual(self.line_texts(got), [["stop."], ["go"]])

    def test_punctuation_off_by_default(self):
        ws = [W("stop.", 0, .1), W("go", .1, .2)]
        got = captions.group_words(ws, max_words=99, max_gap=99, max_span=99)
        self.assertEqual(len(got), 1)

    def test_empty_words_are_dropped_not_kept_as_blanks(self):
        ws = [W("a", 0, .1), W("   ", .1, .2), W("b", .2, .3)]
        flat = [w for ln in captions.group_words(ws, max_gap=99, max_span=99)
                for w in ln]
        self.assertEqual([w.text for w in flat], ["a", "b"])

    def test_no_word_is_ever_lost(self):
        rng = random.Random(7)
        for _ in range(100):
            ws = random_stream(rng, 40)
            kept = [w for w in ws if w.text.strip()]
            got = captions.group_words(ws, max_words=3, max_chars=22,
                                       break_on_punct=True)
            self.assertEqual(sum(len(x) for x in got), len(kept))


class TestItAcceptsBothWordShapes(unittest.TestCase):
    """Dicts (whisper JSON) and objects (Word) — the reason one grouper can
    serve every renderer."""

    def test_dicts(self):
        ws = [{"word": "a", "start": 0, "end": .1},
              {"word": "b", "start": .1, "end": .2}]
        self.assertEqual(len(captions.group_words(ws, max_words=1)), 2)

    def test_objects(self):
        ws = [W("a", 0, .1), W("b", .1, .2)]
        self.assertEqual(len(captions.group_words(ws, max_words=1)), 2)

    def test_accessors_agree(self):
        d = {"word": "hi", "start": 1.0, "end": 2.0}
        o = W("hi", 1.0, 2.0)
        for fn in (captions.word_text, captions.word_start, captions.word_end):
            self.assertEqual(fn(d), fn(o))

    def test_a_dict_using_text_instead_of_word_still_works(self):
        self.assertEqual(captions.word_text({"text": "hi"}), "hi")

    def test_build_ass_handles_objects_too(self):
        ass = captions.build_ass([W("hello", 0, .4), W("world", .4, .9)])
        self.assertIn("HELLO", ass)
        self.assertIn("Dialogue: 0,", ass)


if __name__ == "__main__":
    unittest.main()
