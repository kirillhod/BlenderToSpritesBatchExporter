import os
import sys
import tempfile
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

    def test_name_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = self.make_output_settings(
                tmp, name_template="{collection}_sprite"
            )
            plans = logic.plan_output_paths(["Body"], settings)
            self.assertTrue(plans[0].path.endswith("Body_sprite.png"))
            self.assertFalse(plans[0].skipped)

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
        self.assertEqual(item.name, "Sprite")

        logic.restore_node(node, snapshot)
        self.assertEqual(node.directory, "//out")
        self.assertEqual(node.file_name, "Sprite")
        self.assertEqual(item.name, "Sprite")


class PresetTest(unittest.TestCase):
    def make_settings(self):
        return SimpleNamespace(
            output_dir="//sprites/",
            file_format="PNG",
            color_mode="RGBA",
            color_depth="8",
            use_transparent=True,
            use_compositor_nodes=True,
            node_naming="AUTO",
            node_override_base=False,
            write_main_output=False,
            nodes_connected_only=True,
            overwrite_policy="ASK",
            camera_axis="TOP",
            camera_margin=10.0,
            auto_cleanup_camera=True,
            padding_mode="PIXELS",
            padding_pixels=16,
            padding_units=0.1,
            pixels_per_unit=100.0,
            resolution_multiple=1,
            square_output=False,
            min_resolution=1,
            max_resolution=0,
            isolation_mode="EXCLUDE",
            keep_lights=True,
            export_source="ALL",
            skip_empty=True,
            name_template="{collection}",
        )

    def test_export_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "preset.json")
            settings = self.make_settings()
            settings.pixels_per_unit = 32.0
            settings.name_template = "{collection}_sprite"
            settings.preset_description = "My pixel preset"
            logic.export_preset(settings, path)
            values, ignored, version, description = logic.load_preset(path)
            self.assertEqual(version, logic.PRESET_VERSION)
            self.assertFalse(ignored)
            self.assertEqual(values["pixels_per_unit"], 32.0)
            self.assertEqual(values["name_template"], "{collection}_sprite")
            self.assertEqual(description, "My pixel preset")

            target = self.make_settings()
            ignored = logic.apply_preset(target, values)
            self.assertFalse(ignored)
            self.assertEqual(target.pixels_per_unit, 32.0)

    def test_export_accepts_explicit_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "preset.json")
            settings = self.make_settings()
            logic.export_preset(settings, path, description="Custom description")
            _values, _ignored, _version, description = logic.load_preset(path)
            self.assertEqual(description, "Custom description")

    def test_unknown_fields_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "preset.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"version": 1, "values": {"unknown": 1}}')
            values, ignored, version, description = logic.load_preset(path)
            self.assertEqual(version, 1)
            self.assertEqual(ignored, ["unknown"])
            self.assertEqual(values, {"unknown": 1})
            self.assertEqual(description, "")

    def test_wrong_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "preset.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"version": 99, "values": {}}')
            with self.assertRaises(ValueError):
                logic.load_preset(path)


class ProblemCollectorTest(unittest.TestCase):
    def test_deduplicates_and_sorts(self):
        collector = logic.ProblemCollector()
        collector.add("WARNING", "b", "second")
        collector.add("ERROR", "a", "first")
        collector.add("WARNING", "b", "second")
        collector.add("INFO", "c", "third", collection="Body")
        items = collector.items()
        self.assertEqual([item.severity for item in items], ["ERROR", "WARNING", "INFO"])
        self.assertEqual(len(items), 3)
        self.assertEqual(collector.counts(), {"ERROR": 1, "WARNING": 1, "INFO": 1})
        self.assertTrue(items[2].as_text().startswith("[INFO] c (Body)"))


class FakeOutputFormat:
    def __init__(self, file_format="OPEN_EXR_MULTILAYER"):
        self.file_format = file_format


class FakeOutputItem:
    def __init__(self, name):
        self.name = name


class FakeOutputNode:
    _counter = 0

    def __init__(self, name, file_name, directory, items=("Sprite",)):
        FakeOutputNode._counter += 1
        self.name = name
        self.file_name = file_name
        self.directory = directory
        self.format = FakeOutputFormat()
        self.file_output_items = [FakeOutputItem(item) for item in items]
        self.id_data = SimpleNamespace(library=None)
        self._key = ("node", name, FakeOutputNode._counter)

    def as_pointer(self):
        return FakeOutputNode._counter


class NodeOutputPlanTest(unittest.TestCase):
    def make_node_settings(self, output_dir, **overrides):
        values = {
            "output_dir": output_dir,
            "node_override_base": True,
            "node_naming": "AUTO",
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_auto_uses_collection_and_socket(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = FakeOutputNode("File Output", "Sprite", "//old")
            nodes = {node._key: node}
            settings = self.make_node_settings(tmp)
            plans = logic.plan_node_output_paths(["Body"], "AUTO", settings, nodes)
            self.assertEqual(len(plans), 1)
            plan = plans[0]
            self.assertEqual(plan.layout, "PREFIX")
            self.assertEqual(plan.socket_name, "Sprite")
            self.assertEqual(plan.file_name, "Body_Sprite")
            self.assertEqual(
                os.path.normpath(plan.path),
                os.path.normpath(os.path.join(tmp, "Body_Sprite.exr")),
            )
            self.assertTrue(plan.directory.endswith(os.sep) or plan.directory.endswith("/"))

    def test_auto_prefixes_every_node_with_socket(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = FakeOutputNode("Beauty", "Beauty", "//old", items=("Beauty",))
            second = FakeOutputNode("Mask", "Mask", "//old", items=("Mask",))
            nodes = {first._key: first, second._key: second}
            settings = self.make_node_settings(tmp)
            plans = logic.plan_node_output_paths(["Body"], "AUTO", settings, nodes)
            self.assertTrue(all(plan.layout == "PREFIX" for plan in plans))
            self.assertEqual(
                sorted(os.path.basename(plan.path) for plan in plans),
                ["Body_Beauty.exr", "Body_Mask.exr"],
            )

    def test_socket_name_is_used_not_node_name_or_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = FakeOutputNode("Node Name", "Node File", "//old", items=("Socket",))
            settings = self.make_node_settings(tmp)
            plans = logic.plan_node_output_paths(
                ["Body"], "PREFIX", settings, {node._key: node}
            )
            self.assertEqual(plans[0].file_name, "Body_Socket")
            self.assertNotIn("Node Name", plans[0].file_name)
            self.assertNotIn("Node File", plans[0].file_name)

    def test_prefix_does_not_duplicate_collection_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = FakeOutputNode("File Output", "Body", "//old", items=("Body",))
            settings = self.make_node_settings(tmp, node_naming="PREFIX")
            plans = logic.plan_node_output_paths(
                ["Body"], "PREFIX", settings, {node._key: node}
            )
            self.assertEqual(plans[0].file_name, "Body")
            self.assertTrue(any("already contains" in note for note in plans[0].notes))

    def test_apply_plan_does_not_rename_sockets(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = FakeOutputNode(
                "File Output", "Sprite", "//old", items=("Beauty", "Mask")
            )
            settings = self.make_node_settings(tmp, node_naming="PREFIX")
            plans = logic.plan_node_output_paths(
                ["Body"], "PREFIX", settings, {node._key: node}
            )
            self.assertTrue(logic.apply_node_output_plan(node, plans[0]))
            self.assertEqual(node.file_name, "Body_Beauty_Mask")
            self.assertEqual([item.name for item in node.file_output_items], ["Beauty", "Mask"])

    def test_subfolder_uses_socket_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = FakeOutputNode("File Output", "Sprite", "//old", items=("Sprite",))
            settings = self.make_node_settings(tmp, node_naming="SUBFOLDER")
            plans = logic.plan_node_output_paths(
                ["Body"], "SUBFOLDER", settings, {node._key: node}
            )
            self.assertEqual(plans[0].file_name, "Sprite")
            self.assertEqual(
                os.path.normpath(plans[0].path),
                os.path.normpath(os.path.join(tmp, "Body", "Sprite.exr")),
            )

    def test_no_socket_falls_back_to_node_file_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = FakeOutputNode("File Output", "{blend_name}", "//old", items=())
            settings = self.make_node_settings(tmp, node_naming="SUBFOLDER")
            self.assertEqual(logic.node_raw_file_name(node), "{blend_name}")
            self.assertEqual(logic.node_authored_file_name(node), "Unsaved")
            plans = logic.plan_node_output_paths(
                ["Body"], "SUBFOLDER", settings, {node._key: node}
            )
            self.assertTrue(plans[0].path.endswith("Unsaved.exr"))
            self.assertEqual(plans[0].file_name, "{blend_name}")

    def test_layout_resolution(self):
        self.assertEqual(logic.resolve_node_layout("AUTO", [object()]), "PREFIX")
        self.assertEqual(logic.resolve_node_layout("AUTO", [object(), object()]), "PREFIX")
        self.assertEqual(logic.resolve_node_layout("FILENAME", [object(), object()]), "FILENAME")
        self.assertEqual(logic.resolve_node_layout("UNKNOWN", [object()]), "PREFIX")

    def test_duplicate_node_paths_are_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = FakeOutputNode("First", "Same", "//old", items=("Sprite",))
            second = FakeOutputNode("Second", "Same", "//old", items=("Sprite",))
            settings = self.make_node_settings(tmp)
            plans = logic.plan_node_output_paths(
                ["Body"],
                "SUBFOLDER",
                settings,
                {first._key: first, second._key: second},
            )
            self.assertTrue(plans[1].collision_with)
            self.assertTrue(plans[1].notes)

    def test_ask_allow_existing_skips_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "Body.png")
            with open(path, "wb") as handle:
                handle.write(b"x")
            settings = SimpleNamespace(
                output_dir=tmp,
                file_format="PNG",
                color_mode="RGBA",
                color_depth="8",
            )
            plans = logic.plan_output_paths(["Body"], settings)
            plans, errors, conflicts, _ = logic.apply_overwrite_policy(
                plans, "ASK", headless=False, allow_existing=True
            )
            self.assertFalse(errors)
            self.assertFalse(conflicts)
            self.assertFalse(plans[0].skipped)


if __name__ == "__main__":
    unittest.main()
