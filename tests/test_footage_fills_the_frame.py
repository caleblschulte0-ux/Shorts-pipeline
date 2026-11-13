"""Cut-ins and montage shots fill the frame like the clip does, a multi-
camera source is never split with one pair of boxes, and a reply with two
JSON objects is read, not a crash (Baller Bro, 2026-11-13: every post with
a montage was held: "the highlights play tiny in a letterbox", "a split
crop shows an empty table and an arm for 25 seconds"; and one to three
posts a run died as "render failed: JSONDecodeError: Extra data")."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from third_capture import cut_in, outro, shot_plan
from third_capture.author import one_object


def _letterboxed_reel(path: Path) -> None:
    """640x360 with 60px black bars top and bottom, a white box moving
    across the right of the picture."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
         "color=c=gray:s=640x240:d=3:r=30", "-vf",
         "drawbox=x='400+40*sin(t*6)':y=60:w=60:h=80:c=white:t=fill,"
         "pad=640:360:0:60:black", "-pix_fmt", "yuv420p", str(path)],
        check=True)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_a_letterboxed_reel_is_cropped_to_its_picture_and_its_motion(tmp_path):
    pytest.importorskip("cv2")
    reel = tmp_path / "reel.mp4"
    _letterboxed_reel(reel)
    crop = shot_plan.fill_crop(reel)
    assert crop is not None
    w, h, x, y = crop
    assert 50 <= y <= 64 and 232 <= h <= 252, "the black bars stay in"
    assert w < 640 * 0.6, "still the whole width shrunk into a blur"
    assert x <= 400 <= x + w, "the crop misses what moves"


def test_the_crop_reaches_both_filters():
    fc = outro.graph(2, [3.0, 3.0], 10.0, 1080, 1920, None, "clean",
                     [(180, 240, 300, 60), None])
    assert "[1:v]crop=180:240:300:60," in fc
    assert "[2:v]setpts" in fc
    item = {"at": 4.0, "secs": 2.0, "crop": (180, 240, 300, 60)}
    assert "[3:v]crop=180:240:300:60," in cut_in.overlay("v0", 3, item,
                                                         1080, 1920, "v1")
    assert "[3:v]setpts" in cut_in.overlay("v0", 3, {"at": 4.0, "secs": 2.0},
                                           1080, 1920, "v1")


class _Face:
    presence, cx, cy = 0.9, 1500.0, 500.0

    def med_h(self):
        return 300.0


def _an(cuts):
    det = [1.0] * 1920
    return {"sw": 1920, "sh": 1080, "subjects": [_Face()],
            "col_detail": det, "cuts": cuts}


def test_one_pair_of_boxes_is_never_laid_over_several_cameras():
    single = shot_plan.face_and_content(_an([]))
    assert single is not None, "the one-camera case this layout is for"
    assert shot_plan.face_and_content(_an([4.2, 9.8])) is None


def test_two_objects_in_a_reply_is_the_last_one():
    assert one_object('{"a": 1}\n\n{"a": 2}') == {"a": 2}
    assert one_object('ok: {"x": "{not a brace}"} done') == {"x": "{not a brace}"}
    with pytest.raises(ValueError):
        one_object("no json here")
