import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

import stub_bpy  # noqa: E402

stub_bpy.install()

import blender_to_sprites_batch_exporter as addon  # noqa: E402
from blender_to_sprites_batch_exporter import logic, properties  # noqa: E402


class RegistrationContractTest(unittest.TestCase):
    def test_bl_info(self):
        self.assertEqual(addon.bl_info["version"], (1, 3, 1))
        self.assertEqual(addon.bl_info["blender"], (5, 2, 0))

    def test_operator_ids(self):
        operators = {
            cls.bl_idname for cls in addon.classes if hasattr(cls, "bl_idname") and cls.bl_idname.startswith("bts.")
            and "PT_" not in cls.__name__
        }
        self.assertEqual(
            operators,
            {
                "bts.batch_export",
                "bts.preview_camera",
                "bts.cleanup",
                "bts.restore_collections",
                "bts.open_output_folder",
            },
        )

    def test_panel_ids(self):
        panels = {
            cls.bl_idname for cls in addon.classes if cls.__name__.startswith("BTS_PT_")
        }
        self.assertEqual(
            panels,
            {
                "BTS_PT_main",
                "BTS_PT_source",
                "BTS_PT_camera",
                "BTS_PT_resolution",
                "BTS_PT_output",
            },
        )

    def test_settings_properties(self):
        expected = {
            "output_dir",
            "file_format",
            "color_mode",
            "color_depth",
            "use_transparent",
            "use_compositor_nodes",
            "node_naming",
            "node_override_base",
            "write_main_output",
            "nodes_connected_only",
            "use_prefix_fallback",
            "overwrite_policy",
            "camera_axis",
            "camera_margin",
            "auto_cleanup_camera",
            "padding_mode",
            "padding_pixels",
            "padding_units",
            "pixels_per_unit",
            "resolution_multiple",
            "square_output",
            "min_resolution",
            "max_resolution",
            "isolation_mode",
            "keep_collections",
            "keep_lights",
            "export_source",
            "skip_empty",
        }
        self.assertEqual(set(properties.BTS_Settings.__annotations__), expected)

    def test_logic_is_ui_free(self):
        source = Path(logic.__file__).read_text(encoding="utf-8")
        self.assertNotIn("from .ui", source)
        self.assertNotIn("from .operators", source)
        self.assertNotIn("import .ui", source)
        self.assertNotIn("import .operators", source)


if __name__ == "__main__":
    unittest.main()
