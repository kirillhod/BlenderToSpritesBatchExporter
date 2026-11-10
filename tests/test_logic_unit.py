import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

import stub_bpy  # noqa: E402

stub_bpy.install()

from blender_to_sprites_batch_exporter import logic  # noqa: E402


def make_settings(**overrides):
    values = {
        "camera_axis": "TOP",
        "pixels_per_unit": 10.0,
        "padding_mode": "PIXELS",
        "padding_pixels": 0,
        "padding_units": 0.0,
        "square_output": False,
        "min_resolution": 1,
        "max_resolution": 0,
        "resolution_multiple": 1,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class PathHelpersTest(unittest.TestCase):
    def test_sanitize_filename(self):
        self.assertEqual(logic.sanitize_filename("A/B\\C"), "A_B_C")
        self.assertEqual(logic.sanitize_filename('<>:"|?*'), "untitled")
        self.assertEqual(logic.sanitize_filename("  name.  "), "name")
        self.assertEqual(logic.sanitize_filename("Sprite Name"), "Sprite Name")
        self.assertEqual(logic.sanitize_filename("\0bad"), "bad")

    def test_safe_join(self):
        self.assertEqual(logic.safe_join("//out/", "Body"), "//out/Body")
        self.assertEqual(logic.safe_join("C:\\out", "Body"), "C:/out/Body")
        self.assertEqual(logic.safe_join("", "Body"), "Body")
        self.assertEqual(logic.safe_join("//out", "", "Body"), "//out/Body")

    def test_ensure_slash(self):
        self.assertEqual(logic.ensure_slash(""), "//")
        self.assertEqual(logic.ensure_slash("C:\\out"), "C:/out/")
        self.assertEqual(logic.ensure_slash("//out/"), "//out/")

    def test_split_base(self):
        self.assertEqual(logic.split_base("//sprites/"), ("//sprites", ""))
        self.assertEqual(logic.split_base("//sprites/a.png"), ("//sprites", "a.png"))
        self.assertEqual(logic.split_base("/"), ("/", ""))
        self.assertEqual(logic.split_base("C:/x"), ("C:", "x"))

    def test_make_relative_slot(self):
        self.assertEqual(logic.make_relative_slot("//foo/bar"), "foo/bar")
        self.assertEqual(logic.make_relative_slot("C:\\foo\\bar"), "foo/bar")
        self.assertEqual(logic.make_relative_slot("../foo"), "foo")
        self.assertEqual(logic.make_relative_slot("./foo"), "foo")

    def test_slot_path_is_absolute(self):
        self.assertTrue(logic.slot_path_is_absolute("//foo"))
        self.assertTrue(logic.slot_path_is_absolute("/foo"))
        self.assertTrue(logic.slot_path_is_absolute("C:/foo"))
        self.assertFalse(logic.slot_path_is_absolute("foo/bar"))
        self.assertFalse(logic.slot_path_is_absolute(""))

    def test_unique_dirs(self):
        self.assertEqual(logic.unique_dirs(["a", "a/", "", None]), ["a/"])
        self.assertEqual(logic.unique_dirs(["a\\b", "a/b"]), ["a/b/"])

    def test_is_relative_unsaved(self):
        import bpy

        bpy.data.is_saved = False
        self.assertTrue(logic.is_relative_unsaved("//sprites/"))
        self.assertFalse(logic.is_relative_unsaved("C:/sprites/"))
        bpy.data.is_saved = True
        self.assertFalse(logic.is_relative_unsaved("//sprites/"))

    def test_ensure_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "nested", "dir")
            self.assertTrue(logic.ensure_dir(target))
            self.assertTrue(os.path.isdir(target))

    def test_prefix_new_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "render.png")
            with open(path, "wb") as handle:
                handle.write(b"x")
            renamed = logic.prefix_new_files(
                [tmp],
                "Body",
                before_files=set(),
                start_time=time.time() - 5.0,
                extensions={".png"},
            )
            self.assertEqual(renamed, 1)
            self.assertTrue(os.path.exists(os.path.join(tmp, "Body_render.png")))
            self.assertFalse(os.path.exists(path))


class FrameTest(unittest.TestCase):
    def test_top_frame(self):
        frame = logic.compute_frame(
            logic.mathutils.Vector((0, 0, 0)),
            logic.mathutils.Vector((1, 2, 0)),
            make_settings(),
        )
        self.assertEqual((frame["res_x"], frame["res_y"]), (10, 20))
        self.assertAlmostEqual(frame["ortho_scale"], 2.0)
        self.assertAlmostEqual(frame["center"][0], 0.5)
        self.assertAlmostEqual(frame["center"][1], 1.0)

    def test_front_frame(self):
        frame = logic.compute_frame(
            logic.mathutils.Vector((0, 0, 0)),
            logic.mathutils.Vector((1, 2, 3)),
            make_settings(camera_axis="FRONT"),
        )
        self.assertEqual((frame["res_x"], frame["res_y"]), (10, 30))

    def test_square_output(self):
        frame = logic.compute_frame(
            logic.mathutils.Vector((0, 0, 0)),
            logic.mathutils.Vector((1, 2, 0)),
            make_settings(square_output=True),
        )
        self.assertEqual((frame["res_x"], frame["res_y"]), (20, 20))

    def test_resolution_multiple(self):
        frame = logic.compute_frame(
            logic.mathutils.Vector((0, 0, 0)),
            logic.mathutils.Vector((1, 2, 0)),
            make_settings(resolution_multiple=8),
        )
        self.assertEqual((frame["res_x"], frame["res_y"]), (16, 24))

    def test_min_and_max_resolution(self):
        bounds_min = logic.mathutils.Vector((0, 0, 0))
        bounds_max = logic.mathutils.Vector((1, 2, 0))
        low = logic.compute_frame(bounds_min, bounds_max, make_settings(min_resolution=50))
        self.assertEqual((low["res_x"], low["res_y"]), (50, 50))
        high = logic.compute_frame(bounds_min, bounds_max, make_settings(max_resolution=15))
        self.assertEqual((high["res_x"], high["res_y"]), (10, 15))

    def test_padding_units(self):
        frame = logic.compute_frame(
            logic.mathutils.Vector((0, 0, 0)),
            logic.mathutils.Vector((1, 2, 0)),
            make_settings(padding_mode="UNITS", padding_units=0.1),
        )
        self.assertEqual((frame["res_x"], frame["res_y"]), (12, 22))

    def test_degenerate_bounds(self):
        zero = logic.mathutils.Vector((0, 0, 0))
        frame = logic.compute_frame(zero, zero.copy(), make_settings())
        self.assertEqual((frame["res_x"], frame["res_y"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
