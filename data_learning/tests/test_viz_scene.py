"""Guardrails for the generative scene interpreter."""
from pathlib import Path

from data_learning import charts, viz_director, viz_scene   # noqa: F401
from data_learning.insights import Insight


class _P:
    def __init__(self, label, value, period=None):
        self.label, self.value, self.unit, self.period = label, value, "", period


def _mk(scene, items=None, topic="Topic", unit="", hl="Alpha"):
    ins = Insight.__new__(Insight)
    ins.items = [_P(*it) for it in (items or [("Alpha", 80), ("Beta", 40)])]
    ins.kind = "scene"
    ins.topic = topic
    ins.unit = unit
    ins.baseline = None
    ins.highlight_label = hl
    ins.main_insight = hl + " tops the list"
    ins.scene = scene
    ins.viz_params = {}
    return ins


def test_scene_registered_full_frame():
    assert "scene" in charts.FULLFRAME_RENDERERS
    assert charts.FALLBACK["scene"] == "diorama"


def test_valid_scene_renders(tmp_path=None):
    out = Path(tmp_path or "/tmp/vs_test")
    ins = _mk({"elements": [{"type": "orbit_group", "region": "full"}]},
              items=[("Neptune", 4500), ("Earth", 150), ("Mercury", 58)])
    pat, anchors = charts.render_story_build(ins, out, "vs_ok", frames=3)
    assert pat is not None
    assert ins.kind == "scene"                     # rendered as a scene, no fallback


def test_invalid_scene_falls_back_not_bare():
    out = Path("/tmp/vs_test2")
    bad = {"elements": [{"type": "not_a_type", "region": "full"}]}
    ins = _mk(bad, items=[("A", 9), ("B", 3)])
    assert not viz_scene.validate(bad, ins)
    pat, _ = charts.render_story_build(ins, out, "vs_bad", frames=3)
    # scene invalid -> render_scene None -> FALLBACK chain -> a depiction, never bare
    assert pat is not None
    assert ins.kind not in ("callouts", "bignum", "scene")
    assert viz_director.renderable(ins.kind)


def test_abstract_only_scene_rejected():
    """The lazy look we ban: a lone bar / bubble / number is NOT a valid scene,
    so the director re-picks an image-first depiction instead of shipping it."""
    for bad in (
        {"elements": [{"type": "bar", "region": "center",
                       "data": {"value_from": "star"}}]},
        {"elements": [{"type": "bubble", "region": "center",
                       "data": {"value_from": "star"}}]},
        {"elements": [{"type": "number", "region": "center",
                       "data": {"value_from": "star"}}]},
    ):
        ins = _mk(bad, items=[("Alpha", 30)])
        assert not viz_scene.validate(bad, ins), bad
    # A scene that SHOWS the subject is still valid.
    good = {"elements": [{"type": "fill_object", "region": "center",
                          "subject": "a forest fire",
                          "data": {"value_from": "star"}}]}
    assert viz_scene.validate(good, _mk(good, items=[("Alpha", 30)]))


def test_mechanic_sandbox_rejects_unsafe_code():
    """The AI-invented mechanic path is sandboxed: no imports / dunder / while /
    eval, and it must place a real subject image (never pure abstract shapes)."""
    unsafe = [
        "import os\npaste(None,0,0)",             # import banned
        "while True:\n    paste(None,0,0)",        # loop banned
        "x = (1).__class__\npaste(None,0,0)",      # dunder banned
        "eval('1')\npaste(None,0,0)",              # eval banned
        "d.rectangle([0,0,9,9])",                  # no subject image -> rejected
    ]
    for code in unsafe:
        assert not viz_scene.validate_mechanic({"code": code}), code
    good = ("for i in range(n):\n"
            "    fill_image(images.get(labels[i]), values[i]/vmax*reveal, "
            "RX0+i*300, 500, 240, 600)\n")
    assert viz_scene.validate_mechanic({"mechanic": "m", "code": good})


def test_mechanic_renders_frames(tmp_path=None):
    """A valid mechanic renders the build frames end-to-end (subject images may be
    absent offline -> fill_image degrades to a colored fill, still a depiction)."""
    out = Path(tmp_path or "/tmp/mech_ut")
    code = ("for i in range(n):\n"
            "    fill_image(images.get(labels[i]) if labels[i] in images else None, "
            "clamp(values[i]/vmax)*reveal, RX0+20+i*300, 500, 240, 600, color=ACCENT)\n"
            "    text(str(int(values[i])), RX0+20+i*300+120, 430, size=48, center=True)\n")
    ins = _mk({"mechanic": "tubes", "concept": "fill tubes", "code": code,
               "title": True}, items=[("A", 30), ("B", 10)])
    ins.kind = "mechanic"
    pat, _ = charts.render_story_build(ins, out, "mech_ut", frames=3)
    assert pat is not None


def test_image_cost_counts_cutout_elements():
    spec = {"elements": [
        {"type": "object", "region": "left", "subject": "x", "data": {"value_from": "star"}},
        {"type": "orbit_group", "region": "full"},
        {"type": "fill_object", "region": "center", "subject": "globe", "data": {"value_from": "star"}},
    ]}
    assert viz_scene.image_cost(spec) == 2
