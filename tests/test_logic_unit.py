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


class OutputPlanningTest(unittest.TestCase):
    def make_output_settings(self, output_dir, **overrides):
        values = {
            "output_dir": output_dir,
            "file_format": "PNG",
            "color_mode": "RGBA",
            "color_depth": "8",
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_sanitize_path_component(self):
        self.assertEqual(logic.sanitize_path_component("A/B"), "A_B")
        self.assertEqual(logic.sanitize_path_component("CON"), "_CON")
        self.assertEqual(logic.sanitize_path_component("con.png"), "_con.png")
        self.assertEqual(logic.sanitize_path_component("lpt9"), "_lpt9")
        self.assertEqual(logic.sanitize_path_component(" name. "), "name")
        self.assertEqual(logic.sanitize_path_component("Sprite-Ünïcode"), "Sprite-Ünïcode")

    def test_build_output_path(self):
        base, path = logic.build_output_path("//out/", "Body", "PNG")
        self.assertEqual(base, "//out/Body")
        self.assertEqual(path, "//out/Body.png")
        base, path = logic.build_output_path("//out/", "Body.png", "PNG")
        self.assertEqual(base, "//out/Body")
        self.assertEqual(path, "//out/Body.png")
        base, path = logic.build_output_path("//out/", "CON", "JPEG")
        self.assertEqual(base, "//out/_CON")
        self.assertEqual(path, "//out/_CON.jpg")

    def test_plan_detects_collisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = self.make_output_settings(tmp)
            plans = logic.plan_output_paths(["A/B", "A\\B"], settings)
            self.assertEqual(plans[0].path, plans[1].path)
            self.assertEqual(plans[1].collision_with, "A/B")
            self.assertFalse(plans[0].exists)

    def test_overwrite_policies(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "Body.png"), "wb") as handle:
                handle.write(b"x")
            settings = self.make_output_settings(tmp)

            plans = logic.plan_output_paths(["Body"], settings)
            self.assertTrue(plans[0].exists)

            plans = logic.plan_output_paths(["Body"], settings)
            plans, errors, conflicts, _ = logic.apply_overwrite_policy(
                plans, "ERROR", headless=False, file_format="PNG"
            )
            self.assertEqual(len(errors), 1)
            self.assertTrue(plans[0].skipped)
            self.assertFalse(conflicts)

            plans = logic.plan_output_paths(["Body"], settings)
            plans, errors, conflicts, _ = logic.apply_overwrite_policy(
                plans, "SKIP", headless=False, file_format="PNG"
            )
            self.assertFalse(errors)
            self.assertTrue(plans[0].skipped)

            plans = logic.plan_output_paths(["Body"], settings)
            plans, errors, conflicts, _ = logic.apply_overwrite_policy(
                plans, "OVERWRITE", headless=False, file_format="PNG"
            )
            self.assertFalse(errors)
            self.assertFalse(plans[0].skipped)

            plans = logic.plan_output_paths(["Body"], settings)
            plans, errors, conflicts, _ = logic.apply_overwrite_policy(
                plans, "SUFFIX", headless=False, file_format="PNG"
            )
            self.assertFalse(errors)
            self.assertTrue(plans[0].path.endswith("Body_2.png"))

            plans = logic.plan_output_paths(["Body"], settings)
            plans, errors, conflicts, notes = logic.apply_overwrite_policy(
                plans, "ASK", headless=False, file_format="PNG"
            )
            self.assertFalse(errors)
            self.assertEqual(len(conflicts), 1)
            self.assertFalse(plans[0].skipped)

            plans = logic.plan_output_paths(["Body"], settings)
            plans, errors, conflicts, notes = logic.apply_overwrite_policy(
                plans, "ASK", headless=True, file_format="PNG"
            )
            self.assertEqual(len(errors), 1)
            self.assertTrue(notes)
            self.assertTrue(plans[0].skipped)

    def test_collision_suffix_and_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = self.make_output_settings(tmp)
            plans = logic.plan_output_paths(["A/B", "A\\B"], settings)
            plans, errors, _, _ = logic.apply_overwrite_policy(
                plans, "SUFFIX", headless=False, file_format="PNG"
            )
            self.assertFalse(errors)
            self.assertNotEqual(plans[0].path, plans[1].path)
            self.assertTrue(plans[1].path.endswith("A_B_2.png"))

            plans = logic.plan_output_paths(["A/B", "A\\B"], settings)
            plans, errors, _, _ = logic.apply_overwrite_policy(
                plans, "SKIP", headless=False, file_format="PNG"
            )
            self.assertFalse(errors)
            self.assertTrue(plans[1].skipped)

            plans = logic.plan_output_paths(["A/B", "A\\B"], settings)
            plans, errors, _, _ = logic.apply_overwrite_policy(
                plans, "ERROR", headless=False, file_format="PNG"
            )
            self.assertEqual(len(errors), 1)

    def test_node_names(self):
        collisions = logic.plan_node_name_collisions(["A/B", "A\\B"])
        self.assertEqual(collisions, [("A\\B", "A/B")])

        mapping, errors, skipped = logic.resolve_node_safe_names(
            ["A/B", "A\\B"], "SUFFIX"
        )
        self.assertFalse(errors)
        self.assertEqual(mapping["A\\B"], "A_B_2")

        mapping, errors, skipped = logic.resolve_node_safe_names(
            ["A/B", "A\\B"], "SKIP"
        )
        self.assertEqual(skipped, {"A\\B"})

        mapping, errors, skipped = logic.resolve_node_safe_names(
            ["A/B", "A\\B"], "ERROR"
        )
        self.assertEqual(len(errors), 1)


class ImageSettingsTest(unittest.TestCase):
    def test_valid_png(self):
        settings = SimpleNamespace(file_format="PNG", color_mode="RGBA", color_depth="8")
        file_format, mode, depth, problems = logic.normalize_image_settings(settings)
        self.assertEqual((file_format, mode, depth), ("PNG", "RGBA", "8"))
        self.assertFalse(problems)

    def test_png_32_bit_corrected(self):
        settings = SimpleNamespace(file_format="PNG", color_mode="RGBA", color_depth="32")
        _, _, depth, problems = logic.normalize_image_settings(settings)
        self.assertEqual(depth, "16")
        self.assertEqual(len(problems), 1)

    def test_jpeg_rgba_corrected(self):
        settings = SimpleNamespace(file_format="JPEG", color_mode="RGBA", color_depth="16")
        _, mode, depth, problems = logic.normalize_image_settings(settings)
        self.assertEqual(mode, "RGB")
        self.assertEqual(depth, "8")
        self.assertEqual(len(problems), 2)


class FakeSocket:
    def __init__(self, links=()):
        self.links = list(links)


class FakeNode:
    _counter = 0

    def __init__(self, bl_idname, name, inputs=()):
        FakeNode._counter += 1
        self._pointer = FakeNode._counter
        self.bl_idname = bl_idname
        self.name = name
        self.inputs = list(inputs)
        self.node_tree = None

    def as_pointer(self):
        return self._pointer


class FakeTree:
    _counter = 0

    def __init__(self, nodes=()):
        FakeTree._counter += 1
        self._pointer = FakeTree._counter
        self.nodes = list(nodes)

    def as_pointer(self):
        return self._pointer


class NodeReachabilityTest(unittest.TestCase):
    def test_connected_nodes_only(self):
        source = FakeNode("CompositorNodeRLayers", "Render Layers")
        output = FakeNode(
            "NodeGroupOutput",
            "Group Output",
            [FakeSocket([SimpleNamespace(from_node=source)])],
        )
        connected = FakeNode("CompositorNodeOutputFile", "Connected", [FakeSocket([object()])])
        disconnected = FakeNode("CompositorNodeOutputFile", "Disconnected", [FakeSocket()])
        tree = FakeTree([output, connected, disconnected])
        scene = SimpleNamespace(compositing_node_group=tree)

        all_nodes = logic.collect_file_outputs(scene)
        self.assertEqual(set(all_nodes), {("Connected",), ("Disconnected",)})

        active = logic.collect_file_outputs(scene, reachable_only=True)
        self.assertEqual(set(active), {("Connected",)})


class NodePathTest(unittest.TestCase):
    def test_prefix_updates_directory_file_name_and_items(self):
        item = SimpleNamespace(name="Sprite")
        node = SimpleNamespace(
            name="File Output",
            directory="//out",
            file_name="Sprite",
            file_output_items=[item],
        )
        settings = SimpleNamespace(
            node_naming="PREFIX",
            node_override_base=False,
            output_dir="//out/",
        )
        snapshot = {
            "base_path": "//out",
            "file_name": "Sprite",
            "slot_key": "name",
            "slot_paths": ["Sprite"],
            "library": False,
        }
        target_dir, scan_dirs, needs_prefix, problems = logic.apply_node_paths(
            node, settings, "A/B", snapshot
        )
        self.assertFalse(problems)
        self.assertFalse(needs_prefix)
        self.assertEqual(target_dir, "//out/")
        self.assertEqual(node.directory, "//out/")
        self.assertEqual(node.file_name, "A_B_Sprite")
        self.assertEqual(item.name, "A_B_Sprite")

        logic.restore_node(node, snapshot)
        self.assertEqual(node.directory, "//out")
        self.assertEqual(node.file_name, "Sprite")
        self.assertEqual(item.name, "Sprite")


if __name__ == "__main__":
    unittest.main()
