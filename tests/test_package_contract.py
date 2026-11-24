import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

import stub_bpy  # noqa: E402

stub_bpy.install()

import blender_to_sprites_batch_exporter as addon  # noqa: E402
from blender_to_sprites_batch_exporter import logic, properties, ui  # noqa: E402


class RegistrationContractTest(unittest.TestCase):
    def test_bl_info(self):
        self.assertEqual(addon.bl_info["version"], (3, 1, 2))
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
                "bts.analyze",
                "bts.cancel_export",
                "bts.refresh_targets",
                "bts.targets_all",
                "bts.targets_none",
                "bts.targets_active",
                "bts.activate_target",
                "bts.add_always_include",
                "bts.remove_always_include",
                "bts.copy_report",
                "bts.open_log",
                "bts.apply_preset",
                "bts.save_preset",
                "bts.load_preset",
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
                "BTS_PT_problems",
                "BTS_PT_presets",
                "BTS_PT_report",
            },
        )

    def test_ui_list_ids(self):
        lists = {
            cls.bl_idname for cls in addon.classes if cls.__name__.startswith("BTS_UL_")
        }
        self.assertEqual(
            lists,
            {
                "BTS_UL_Targets",
                "BTS_UL_AlwaysInclude",
                "BTS_UL_Preview",
                "BTS_UL_NodeOutputs",
            },
        )

    def test_settings_properties(self):
        expected = {
            "target_items",
            "always_include_items",
            "preview_items",
            "node_items",
            "target_items_migrated",
            "always_include_migrated",
            "layout_migrated",
            "views_migrated",
            "target_search",
            "active_target_index",
            "active_include_index",
            "active_preview_index",
            "active_node_index",
            "show_path_preview",
            "name_template",
            "last_report",
            "last_log_path",
            "preset_description",
            "debug_log",
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
            "overwrite_policy",
            "camera_axis",
            "view_top",
            "view_bottom",
            "view_front",
            "view_back",
            "view_right",
            "view_left",
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

    def test_target_item_properties(self):
        expected = {
            "name",
            "enabled",
            "size_status",
            "override_view",
            "override_view_seeded",
            "view_top",
            "view_bottom",
            "view_front",
            "view_back",
            "view_right",
            "view_left",
            "override_framing",
            "override_framing_seeded",
            "camera_margin",
            "padding_mode",
            "padding_pixels",
            "padding_units",
            "override_resolution",
            "override_resolution_seeded",
            "pixels_per_unit",
            "resolution_multiple",
            "square_output",
            "min_resolution",
            "max_resolution",
        }
        self.assertEqual(
            set(properties.BTS_TargetItem.__annotations__), expected
        )

    def test_logic_is_ui_free(self):
        sources = [Path(logic.__file__)]
        sources.extend(
            sorted((Path(logic.__file__).parent / "core").glob("*.py"))
        )
        for path in sources:
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("from .ui", source)
            self.assertNotIn("from .operators", source)
            self.assertNotIn("import .ui", source)
            self.assertNotIn("import .operators", source)


class UiTextContractTest(unittest.TestCase):
    def test_static_hints_are_not_drawn(self):
        source = (
            ROOT / "blender_to_sprites_batch_exporter" / "ui.py"
        ).read_text(encoding="utf-8")
        banned = (
            "Examples: {collection}",
            "Use 0.01-0.1 for crisp pixel art.",
            "Details are in the Problems panel.",
            "Run Analyze to validate settings.",
            "Multi-view presets arrive with 2.1.",
            "Light collections are included automatically.",
            "Other objects in light collections may appear in the render.",
            "Enable Also Save Main Render for PNG/JPEG.",
            "Warnings do not block export; errors do.",
            "File Output detection uses the analysis cache.",
            "File name = Collection + socket name.",
            "The node name and label are not used.",
            "An existing collection token is not duplicated.",
            "Compositing is disabled!",
            "Compositing will be disabled during export.",
        )
        for text in banned:
            self.assertNotIn(text, source)

    def test_every_operator_has_a_description(self):
        for cls in addon.classes:
            name = getattr(cls, "bl_idname", "")
            if not name.startswith("bts."):
                continue
            self.assertTrue(
                str(getattr(cls, "bl_description", "") or "").strip(),
                f"{name} has no bl_description",
            )

    def test_log_panel_stays_open_and_only_draws_log_actions(self):
        source = (
            ROOT / "blender_to_sprites_batch_exporter" / "ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn("class BTS_PT_Report(Panel):", source)
        report_source = source.split("class BTS_PT_Report(Panel):", 1)[1]
        self.assertIn('bl_label = "Log"', report_source)
        self.assertNotIn("last_report", report_source)
        self.assertNotIn("open_output_folder", report_source)
        self.assertEqual(ui.BTS_PT_Report.bl_label, "Log")
        self.assertNotIn("bl_options", ui.BTS_PT_Report.__dict__)

    def test_target_list_has_a_fixed_status_column(self):
        source = (
            ROOT / "blender_to_sprites_batch_exporter" / "ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn("_TARGET_NAME_FACTOR", source)
        self.assertIn("row.split(factor=_TARGET_NAME_FACTOR", source)
        self.assertIn('text="Canvas / status"', source)
        self.assertIn("use_property_split = False", source)
        self.assertNotIn("layout.alignment = 'LEFT'", source)
        self.assertNotIn("row.alignment = 'LEFT'", source)

    def test_view_grid_and_collapsible_overrides(self):
        source = (
            ROOT / "blender_to_sprites_batch_exporter" / "ui.py"
        ).read_text(encoding="utf-8")
        camera = source.split("class BTS_PT_Camera", 1)[1].split(
            "class BTS_PT_Resolution", 1
        )[0]
        self.assertIn("_draw_view_grid", camera)
        self.assertNotIn('layout.prop(settings, "camera_axis")', camera)
        self.assertIn('"bts_override_" + group', source)
        self.assertIn('("view", "View"', source)
        self.assertIn('("framing", "Framing"', source)
        self.assertIn('("resolution", "Resolution"', source)
        self.assertIn("layout.panel(", source)
        self.assertNotIn("Using global", source)
        self.assertNotIn('panel_prop(item, "override_', source)

    def test_output_lists_are_compact_and_scrollable(self):
        source = (
            ROOT / "blender_to_sprites_batch_exporter" / "ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"BTS_UL_Preview"', source)
        self.assertIn('"BTS_UL_NodeOutputs"', source)
        self.assertIn('"show_path_preview"', source)
        self.assertIn("_list_rows(visible_rows, 3, 8)", source)
        self.assertIn("_list_rows(count, 1, 4)", source)
        self.assertIn("_list_rows(len(include_items), 1, 3)", source)
        self.assertIn("_list_rows(len(nodes), 1, 3)", source)
        self.assertNotIn("_draw_preview", source)
        self.assertNotIn("active File Output node(s)", source)


class UiHelperTest(unittest.TestCase):
    def test_target_status_explains_canvas_and_skip_reason(self):
        self.assertEqual(ui._target_status_text(""), "")
        self.assertEqual(ui._target_status_text("512x304"), "Canvas 512x304")
        self.assertEqual(
            ui._target_status_text("512x304, 2 views"),
            "Canvas 512x304, 2 views",
        )
        self.assertEqual(
            ui._target_status_text("no renderable geometry"),
            "Skipped: no renderable geometry",
        )

    def test_list_rows_shrink_to_content_and_respect_bounds(self):
        self.assertEqual(ui._list_rows(0, 1, 3), 1)
        self.assertEqual(ui._list_rows(2, 1, 3), 2)
        self.assertEqual(ui._list_rows(50, 1, 3), 3)
        self.assertEqual(ui._list_rows(0, 3, 8), 3)
        self.assertEqual(ui._list_rows(2, 3, 8), 3)
        self.assertEqual(ui._list_rows(50, 3, 8), 8)
        self.assertEqual(ui._list_rows(4, 1, 4), 4)

    def test_compact_target_status_fits_the_status_column(self):
        self.assertEqual(ui._target_status_text("512x304", compact=True), "512x304")
        self.assertEqual(
            ui._target_status_text("no renderable geometry", compact=True),
            "skipped",
        )
        self.assertEqual(ui._target_status_text("", compact=True), "")

    def test_target_filter_keeps_all_items_without_search(self):
        ulist = ui.BTS_UL_Targets()
        ulist.bitflag_filter_item = 1
        data = SimpleNamespace(
            target_search="",
            target_items=[
                SimpleNamespace(name="Body"),
                SimpleNamespace(name="Weapon"),
            ],
        )
        flags, order = ulist.filter_items(None, data, "target_items")
        self.assertEqual(flags, [1, 1])
        self.assertEqual(order, [])
        data.target_search = "weap"
        flags, order = ulist.filter_items(None, data, "target_items")
        self.assertEqual(flags, [0, 1])
        self.assertEqual(order, [])

    def test_wrap_text_keeps_every_character(self):
        text = "C:/a/very/long/path/that/should/not/be/truncated/at/all"
        lines = ui._wrap_text(text, width=20)
        self.assertTrue(all(len(line) <= 20 for line in lines))
        self.assertEqual("".join(lines), text)


if __name__ == "__main__":
    unittest.main()
