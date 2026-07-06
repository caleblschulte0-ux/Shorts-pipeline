"""Guardrails for the viz director + depiction contract.

The operator mandate: NEVER show bare numbers, and no rotation — every segment
depicts, videos vary, and each video has a stand-out. These tests lock that in.
"""
from data_learning import charts, viz_director
from data_learning.insights import Insight


class _P:
    def __init__(self, label, value, period=None):
        self.label, self.value, self.unit, self.period = label, value, "", period


def _mk(kind="rank", items=None, topic="thing", unit="", periods=False,
        authored="", params=None):
    ins = Insight.__new__(Insight)
    items = items or [("Alpha", 80), ("Beta", 40), ("Gamma", 20)]
    ins.items = [_P(l, v, (str(2000 + i) if periods else None))
                 for i, (l, v) in enumerate(items)]
    ins.kind = kind
    ins.topic = topic
    ins.unit = unit
    ins.baseline = None
    ins.highlight_label = items[0][0]
    ins.main_insight = items[0][0] + " tops the list"
    ins.authored_viz = authored
    ins.viz_params = params or {}
    return ins


_BARE = {"callouts", "bignum"}


def test_director_never_selects_bare_numbers():
    videos = [
        [_mk("rank"), _mk("share", unit="percent"),
         _mk("rank", items=[("Texas", 39), ("Ohio", 22)])],
        [_mk("rank", periods=True), _mk("comparison", items=[("A", 9), ("B", 3)])],
        [_mk("rank", items=[("X", 100)])],
    ]
    for inss in videos:
        viz_director.assign(inss, seed=5)
        for ins in inss:
            assert ins.kind not in _BARE, f"selected bare number kind {ins.kind}"
            assert viz_director.renderable(ins.kind), f"unrenderable {ins.kind}"


def test_director_no_repeat_and_has_novelty():
    inss = [_mk("rank", topic=f"thing {i}",
                items=[("A", 80 - i), ("B", 40), ("C", 20)]) for i in range(3)]
    viz_director.assign(inss, seed=9)
    kinds = [i.kind for i in inss]
    # Lazy SHAPE depictions must not repeat; maps/trend/real-photo depictions may
    # (all of those are good, so repeating them beats degrading to junk).
    def _may_repeat(k):
        m = viz_director.KINDS.get(k, {})
        return m.get("place") or m.get("time") or m.get("repeatable")
    non_repeatable = [k for k in kinds if not _may_repeat(k)]
    assert len(non_repeatable) == len(set(non_repeatable)), kinds
    assert any(viz_director.KINDS.get(k, {}).get("novelty") for k in kinds), kinds
    # And never a lazy bare/dots depiction for a real ranking.
    assert not any(k in ("callouts", "bignum") for k in kinds), kinds


def test_fallback_values_are_depictions():
    # No fallback target is ever a bare-number kind.
    for target in charts.FALLBACK.values():
        assert target not in _BARE, target
    # Every full-frame kind's fallback chain ends at a renderable, non-bare kind.
    for kind in charts.FULLFRAME_RENDERERS:
        seen, k, hops = set(), kind, 0
        while k in charts.FULLFRAME_RENDERERS and hops < 5:
            k = charts.FALLBACK.get(k, "bubbles")
            assert k not in seen, f"fallback loop at {kind}"
            seen.add(k)
            hops += 1
        assert k not in _BARE
        assert k in viz_director.CARD_KINDS or k in charts.FULLFRAME_RENDERERS


def test_place_data_always_maps():
    inss = [_mk("rank", items=[("California", 39), ("Texas", 30),
                               ("Florida", 22), ("Ohio", 12)], topic="by state")]
    viz_director.assign(inss, seed=1)
    assert inss[0].kind == "geo_us"
