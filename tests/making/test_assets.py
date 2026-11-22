"""The ready-made scenes: hiding the stand-in's face, and picking up redrawn scenes without a restart."""

import io

from PIL import Image

from storybook.making import assets
from tests.conftest import jpeg


def test_blur_only_changes_the_box():
    from PIL import ImageChops, ImageStat
    original = jpeg((90, 140, 200), (400, 600))
    blurred = assets._blur_box(original, [350, 250, 650, 500])        # the face oval's area (0-1000)
    diff = ImageChops.difference(Image.open(io.BytesIO(original)).convert("L"),
                                 Image.open(io.BytesIO(blurred)).convert("L"))
    inside = ImageStat.Stat(diff.crop((130, 140, 270, 310))).mean[0]
    outside = ImageStat.Stat(diff.crop((0, 450, 400, 600))).mean[0]
    assert inside > 4 * max(outside, 0.5)     # the face's edges are smeared away ...
    assert outside < 2                        # ... and the rest of the picture is untouched


def test_scene_with_the_stand_in_hidden(prepared):
    jpg, hidden = assets.scene_without_face(prepared, "jack", 1)
    assert hidden and jpg[:2] == b"\xff\xd8"


def test_a_redrawn_scene_is_picked_up(prepared, monkeypatch):
    first = assets.plate(prepared, "red", 5)
    rec = prepared.get_record(assets.pk("red"), "PLATE#05")
    keep = {k: v for k, v in rec.items() if k not in ("pk", "sk", "user_id")}
    prepared.put_record(assets.pk("red"), "PLATE#05", {**keep, "made_at": keep["made_at"] + 1})
    try:
        monkeypatch.setattr(assets, "PLATE_RECHECK_SECONDS", 0)
        assert assets.plate(prepared, "red", 5)["made_at"] == first["made_at"] + 1
    finally:
        prepared.put_record(assets.pk("red"), "PLATE#05", keep)
