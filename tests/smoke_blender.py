"""Blender smoke test for Blender To Sprites Batch Exporter.

Run:
    blender -b --factory-startup --python tests/smoke_blender.py

Optional environment variables:
    BTS_REPO             Path to repository root (defaults to parent of tests/).
    BTS_STRICT_CAMERA=1  Also test a user camera named like the temporary one.
    BTS_KEEP_OUTPUT=1    Keep rendered files for inspection.
"""

import os
import re
import sys
import tempfile
import traceback

import bmesh
import bpy


TEMP_CAMERA_NAME = "_BTS_OrthoCamera"


def repo_root():
    env = os.environ.get("BTS_REPO")
    if env:
        return os.path.abspath(env)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_addon():
    root = repo_root()
    if root not in sys.path:
        sys.path.insert(0, root)
    import blender_to_sprites_batch_exporter as addon

    # The module may already be registered when the test is launched from
    # an installed add-on. Register only if the property is missing.
    if not hasattr(bpy.types.Scene, "bts_settings"):
        addon.register()
    return addon


def make_collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def add_cube(collection, name, location=(0.0, 0.0, 0.0), size=1.0):
    mesh = bpy.data.meshes.new(name + "Mesh")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.location = location
    return obj


def add_light(collection, name):
    data = bpy.data.lights.new(name, type="POINT")
    data.energy = 100.0
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = (2.0, -2.0, 4.0)
    return obj


def add_camera(collection, name, location=(10.0, 10.0, 10.0)):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (0.0, 0.0, 0.0)
    return obj


def set_engine(scene):
    for engine in ("BLENDER_WORKBENCH", "BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            return engine
        except TypeError:
            continue
    raise RuntimeError("No supported render engine found")


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def add_root_object(scene):
    """Add a cube directly to the scene collection (not to a target collection)."""
    obj = add_cube(scene.collection, "RootCube", location=(20.0, 20.0, 0.0), size=0.5)
    obj.hide_render = False
    return obj


def run_policy_checks(scene, settings, out_dir):
    """Check every overwrite policy against already rendered files."""
    expected = [os.path.join(out_dir, "Body.png"), os.path.join(out_dir, "Weapon.png")]
    before = {path: os.path.getmtime(path) for path in expected}

    settings.overwrite_policy = "ERROR"
    try:
        result = bpy.ops.bts.batch_export()
    except RuntimeError:
        # Blender raises RuntimeError for a CANCELLED operator that reported errors.
        result = {"CANCELLED"}
    check(result == {"CANCELLED"}, "Error policy did not stop: %r" % (result,))
    for path in expected:
        check(os.path.getmtime(path) == before[path], "Error policy changed a file")

    settings.overwrite_policy = "ASK"
    try:
        result = bpy.ops.bts.batch_export()
    except RuntimeError:
        result = {"CANCELLED"}
    check(result == {"CANCELLED"}, "Ask policy did not stop in background: %r" % (result,))

    settings.overwrite_policy = "SKIP"
    result = bpy.ops.bts.batch_export()
    check(result == {"FINISHED"}, "Skip policy did not finish: %r" % (result,))
    check(
        sorted(os.listdir(out_dir)) == ["Body.png", "Weapon.png"],
        "Skip policy created files: %r" % (sorted(os.listdir(out_dir)),),
    )
    for path in expected:
        check(os.path.getmtime(path) == before[path], "Skip policy changed a file")

    settings.overwrite_policy = "SUFFIX"
    result = bpy.ops.bts.batch_export()
    check(result == {"FINISHED"}, "Suffix policy did not finish: %r" % (result,))
    files = sorted(os.listdir(out_dir))
    check(
        "Body_2.png" in files and "Weapon_2.png" in files,
        "Suffix policy did not add names: %r" % (files,),
    )

    settings.overwrite_policy = "OVERWRITE"
    result = bpy.ops.bts.batch_export()
    check(result == {"FINISHED"}, "Overwrite policy did not finish: %r" % (result,))
    check(
        "Body_3.png" not in os.listdir(out_dir),
        "Overwrite policy added an unexpected suffix",
    )


def run_compositor_test():
    """Render through a connected File Output node and ignore a disconnected one."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon = load_addon()
    scene = bpy.context.scene
    set_engine(scene)
    body = make_collection("Body")
    add_cube(body, "BodyCube")

    out_dir = tempfile.mkdtemp(prefix="bts_nodes_")
    tree = bpy.data.node_groups.new("BTS Compositor", "CompositorNodeTree")
    scene.compositing_node_group = tree
    tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")

    render_layers = tree.nodes.new("CompositorNodeRLayers")
    group_output = tree.nodes.new("NodeGroupOutput")
    active = tree.nodes.new("CompositorNodeOutputFile")
    active.name = "Active Output"
    active.directory = out_dir
    active.file_output_items.new("RGBA", "Sprite")
    tree.links.new(render_layers.outputs["Image"], group_output.inputs["Image"])
    tree.links.new(render_layers.outputs["Image"], active.inputs["Sprite"])

    unused_dir = os.path.join(out_dir, "unused")
    os.makedirs(unused_dir, exist_ok=True)
    unused = tree.nodes.new("CompositorNodeOutputFile")
    unused.name = "Unused Output"
    unused.directory = unused_dir
    unused.file_output_items.new("RGBA", "Unused")

    original_dir = active.directory
    original_file_name = active.file_name
    settings = scene.bts_settings
    settings.output_dir = out_dir
    settings.file_format = "PNG"
    settings.color_mode = "RGBA"
    settings.color_depth = "8"
    settings.use_transparent = True
    settings.use_compositor_nodes = True
    settings.nodes_connected_only = True
    settings.node_naming = "SUBFOLDER"
    settings.node_override_base = True
    settings.write_main_output = False
    settings.export_source = "ALL"
    settings.isolation_mode = "EXCLUDE"
    settings.keep_collections = ""
    settings.keep_lights = False
    settings.skip_empty = True
    settings.auto_cleanup_camera = True
    settings.camera_axis = "TOP"
    settings.padding_mode = "PIXELS"
    settings.padding_pixels = 0
    settings.pixels_per_unit = 16.0
    settings.resolution_multiple = 1
    settings.square_output = False
    settings.min_resolution = 1
    settings.max_resolution = 0
    settings.overwrite_policy = "OVERWRITE"

    from blender_to_sprites_batch_exporter import logic

    plans = logic.plan_node_output_paths(
        ["Body"], "FILENAME", settings, {("Active Output",): active}
    )
    check(
        os.path.normpath(plans[0].path)
        == os.path.normpath(os.path.join(out_dir, "Body.exr")),
        "Collection Only plan path: %r" % (plans[0].path,),
    )
    auto_one = logic.plan_node_output_paths(
        ["Body"], "AUTO", settings, {("Active Output",): active}
    )
    check(auto_one[0].layout == "PREFIX", "AUTO did not choose Collection + Socket")
    check(
        os.path.normpath(auto_one[0].path)
        == os.path.normpath(os.path.join(out_dir, "Body_Sprite.exr")),
        "AUTO socket plan path: %r" % (auto_one[0].path,),
    )
    auto_two = logic.plan_node_output_paths(
        ["Body"],
        "AUTO",
        settings,
        {("Active Output",): active, ("Unused Output",): unused},
    )
    check(
        sorted(os.path.basename(plan.path) for plan in auto_two)
        == ["Body_Sprite.exr", "Body_Unused.exr"],
        "AUTO multi-node paths: %r" % ([plan.path for plan in auto_two],),
    )

    result = bpy.ops.bts.batch_export()
    check(result == {"FINISHED"}, "Compositor export did not finish: %r" % (result,))
    target_dir = os.path.join(out_dir, "Body")
    check(os.path.isdir(target_dir), "Subfolder was not created: %r" % (target_dir,))
    rendered = [
        name for name in os.listdir(target_dir) if name.lower().endswith(".exr")
    ]
    check(rendered, "File Output node did not write a file: %r" % (target_dir,))
    check(
        rendered == ["Sprite.exr"],
        "Subfolder file must use the socket name: %r" % (rendered,),
    )
    check(active.directory == original_dir, "Node directory was not restored")
    check(
        [item.name for item in active.file_output_items] == ["Sprite"],
        "Node item name was not restored",
    )
    check(unused.directory == unused_dir, "Disconnected node was modified")
    check(not os.listdir(unused_dir), "Disconnected node wrote a file")

    # PREFIX mode must change the output file name, not only the directory.
    prefix_dir = os.path.join(out_dir, "prefix")
    os.makedirs(prefix_dir, exist_ok=True)
    settings.output_dir = prefix_dir
    settings.node_naming = "PREFIX"
    result = bpy.ops.bts.batch_export()
    check(result == {"FINISHED"}, "Prefix export did not finish: %r" % (result,))
    prefix_files = [
        name for name in os.listdir(prefix_dir) if name.lower().endswith(".exr")
    ]
    check(prefix_files == ["Body_Sprite.exr"], "Prefix file names: %r" % (prefix_files,))
    check(active.directory == original_dir, "Prefix mode did not restore directory")
    check(active.file_name == original_file_name, "Prefix mode did not restore file name")

    # Existing node outputs must obey the overwrite policy in preflight.
    settings.overwrite_policy = "ERROR"
    try:
        result = bpy.ops.bts.batch_export()
    except RuntimeError:
        result = {"CANCELLED"}
    check(
        result == {"CANCELLED"},
        "Node Error policy did not stop: %r" % (result,),
    )
    settings.overwrite_policy = "OVERWRITE"

    # Don't Modify is safe only for one collection; preflight must reject a
    # multi-target run before rendering.
    weapon = make_collection("Weapon")
    add_cube(weapon, "WeaponCube", location=(4.0, 0.0, 0.0), size=0.5)
    settings.node_naming = "NONE"
    analysis, _ = logic.analyze_scene(bpy.context, settings, use_cache=False)
    check(
        any(problem.code == "node_manual_multi_target" for problem in analysis.errors),
        "Don't Modify multi-target preflight error is missing: %r"
        % ([problem.code for problem in analysis.errors],),
    )

    for root, _, names in os.walk(out_dir):
        for name in names:
            os.remove(os.path.join(root, name))
    for root, dirs, _ in os.walk(out_dir, topdown=False):
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(out_dir)


def run_analysis_and_cancel_test():
    """Preflight must not render, the cache must invalidate, and cancel must restore."""
    from blender_to_sprites_batch_exporter import logic

    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon = load_addon()
    scene = bpy.context.scene
    set_engine(scene)
    body = make_collection("Body")
    add_cube(body, "BodyCube")

    out_dir = tempfile.mkdtemp(prefix="bts_analysis_")
    settings = scene.bts_settings
    settings.output_dir = out_dir
    settings.file_format = "PNG"
    settings.color_mode = "RGBA"
    settings.color_depth = "8"
    settings.use_compositor_nodes = False
    settings.export_source = "ALL"
    settings.isolation_mode = "EXCLUDE"
    settings.keep_lights = False
    settings.skip_empty = True
    settings.overwrite_policy = "OVERWRITE"
    settings.camera_axis = "TOP"
    settings.padding_mode = "PIXELS"
    settings.padding_pixels = 0
    settings.pixels_per_unit = 16.0
    settings.resolution_multiple = 1
    settings.square_output = False
    settings.min_resolution = 1
    settings.max_resolution = 0

    analysis, cached = logic.analyze_scene(bpy.context, settings, use_cache=False)
    check(not analysis.errors, "Preflight reported errors: %r" % (analysis.problems,))
    check(cached is False, "First analysis unexpectedly came from cache")
    check(os.listdir(out_dir) == [], "Preflight rendered files")

    result = bpy.ops.bts.analyze()
    check(result == {"FINISHED"}, "Analyze operator failed: %r" % (result,))
    check(
        logic.get_cached_analysis(bpy.context, settings) is not None,
        "Analyze operator did not fill the cache",
    )

    analysis, cached = logic.analyze_scene(bpy.context, settings, use_cache=True)
    check(cached is True, "Second analysis did not use the cache")
    settings.output_dir = out_dir + "_changed"
    analysis, cached = logic.analyze_scene(bpy.context, settings, use_cache=True)
    check(cached is False, "Setting change did not invalidate the cache")
    settings.output_dir = out_dir

    original_camera = scene.camera
    analysis, _ = logic.analyze_scene(bpy.context, settings, use_cache=False)
    job = logic.BatchJob(bpy.context, settings, analysis)
    check(job.start(), "BatchJob did not start")
    job.request_cancel()
    job.step()
    result = job.finish()
    check(result.cancelled, "Cancelled job did not report cancellation")
    check(result.rendered == 0, "Cancelled job rendered a collection")
    check(scene.camera == original_camera, "Cancelled job did not restore the camera")
    check(os.listdir(out_dir) == [], "Cancelled job wrote files")

    os.rmdir(out_dir)


def run_target_list_test():
    """Target items drive export; name templates and presets are portable."""
    from blender_to_sprites_batch_exporter import logic

    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon = load_addon()
    scene = bpy.context.scene
    set_engine(scene)
    body = make_collection("Body")
    weapon = make_collection("Weapon")
    add_cube(body, "BodyCube")
    add_cube(weapon, "WeaponCube", location=(4.0, 0.0, 0.0), size=0.5)

    out_dir = tempfile.mkdtemp(prefix="bts_targets_")
    settings = scene.bts_settings
    settings.output_dir = out_dir
    settings.file_format = "PNG"
    settings.color_mode = "RGBA"
    settings.color_depth = "8"
    settings.use_compositor_nodes = False
    settings.export_source = "ALL"
    settings.isolation_mode = "EXCLUDE"
    settings.keep_lights = False
    settings.skip_empty = True
    settings.overwrite_policy = "OVERWRITE"
    settings.camera_axis = "TOP"
    settings.padding_mode = "PIXELS"
    settings.padding_pixels = 0
    settings.pixels_per_unit = 16.0
    settings.resolution_multiple = 1
    settings.square_output = False
    settings.min_resolution = 1
    settings.max_resolution = 0

    logic.rebuild_target_items(bpy.context, settings)
    names = [item.name for item in settings.target_items]
    check("Body" in names and "Weapon" in names, "Target list: %r" % (names,))

    body_layer = logic.find_layer_collection(bpy.context.view_layer, "Body")
    bpy.context.view_layer.active_layer_collection = body_layer
    bpy.ops.bts.add_always_include()
    check(
        any(item.name == "Body" for item in settings.always_include_items),
        "Always Include was not added",
    )
    settings.active_include_index = 0
    bpy.ops.bts.remove_always_include()
    check(
        not any(item.name == "Body" for item in settings.always_include_items),
        "Always Include was not removed",
    )
    bpy.ops.bts.targets_none()
    check(not any(item.enabled for item in settings.target_items), "Targets None failed")
    bpy.ops.bts.targets_all()
    check(all(item.enabled for item in settings.target_items), "Targets All failed")
    bpy.ops.bts.targets_active()
    enabled_names = [
        item.name for item in settings.target_items if item.enabled
    ]
    check(enabled_names == ["Body"], "Targets Active: %r" % (enabled_names,))
    bpy.ops.bts.targets_all()

    body_item = next(item for item in settings.target_items if item.name == "Body")
    body_item.enabled = False
    analysis, _ = logic.analyze_scene(bpy.context, settings, use_cache=False)
    check(
        [target.name for target in analysis.targets] == ["Weapon"],
        "Disabled target was exported: %r"
        % ([target.name for target in analysis.targets],),
    )
    body_item.enabled = True

    settings.name_template = "{collection}_sprite"
    analysis, _ = logic.analyze_scene(bpy.context, settings, use_cache=False)
    plan = analysis.main_plan_by_name["Body"]
    check(
        plan.path.endswith("Body_sprite.png"),
        "Name template path: %r" % (plan.path,),
    )

    settings.pixels_per_unit = 16.0
    settings.preset_description = "Custom pixel preset"
    logic.apply_preset(settings, logic.BUILTIN_PRESETS["Pixel Art Top"])
    check(abs(settings.pixels_per_unit - 32.0) < 1e-6, "Preset was not applied")
    preset_file = os.path.join(out_dir, "preset.json")
    logic.export_preset(settings, preset_file)
    settings.pixels_per_unit = 1.0
    values, ignored, version, description = logic.load_preset(preset_file)
    check(version == logic.PRESET_VERSION and not ignored, "Preset metadata")
    check(description == "Custom pixel preset", "Preset description: %r" % (description,))
    logic.apply_preset(settings, values)
    check(abs(settings.pixels_per_unit - 32.0) < 1e-6, "Preset was not loaded")

    result = bpy.ops.bts.apply_preset(preset="Pixel Art Top")
    check(result == {"FINISHED"}, "Apply preset operator: %r" % (result,))
    check(abs(settings.pixels_per_unit - 32.0) < 1e-6, "Apply preset did not run")
    check(
        settings.preset_description == logic.builtin_preset_description("Pixel Art Top"),
        "Built-in preset description was not applied",
    )
    result = bpy.ops.bts.save_preset(filepath=preset_file)
    check(result == {"FINISHED"}, "Save preset operator: %r" % (result,))
    settings.pixels_per_unit = 1.0
    settings.preset_description = ""
    result = bpy.ops.bts.load_preset(filepath=preset_file)
    check(result == {"FINISHED"}, "Load preset operator: %r" % (result,))
    check(abs(settings.pixels_per_unit - 32.0) < 1e-6, "Load preset did not apply")
    check(settings.preset_description, "Load preset did not restore description")

    for name in os.listdir(out_dir):
        os.remove(os.path.join(out_dir, name))
    os.rmdir(out_dir)


def run_collision_test():
    """Collections that sanitize to the same name must not overwrite each other."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon = load_addon()
    scene = bpy.context.scene
    set_engine(scene)
    col_a = make_collection("A/B")
    col_b = make_collection("A\\B")
    add_cube(col_a, "CollisionCubeA")
    add_cube(col_b, "CollisionCubeB", location=(2.0, 0.0, 0.0))

    out_dir = tempfile.mkdtemp(prefix="bts_collision_")
    settings = scene.bts_settings
    settings.output_dir = out_dir
    settings.file_format = "PNG"
    settings.color_mode = "RGBA"
    settings.color_depth = "8"
    settings.use_transparent = True
    settings.use_compositor_nodes = False
    settings.export_source = "ALL"
    settings.isolation_mode = "EXCLUDE"
    settings.keep_collections = ""
    settings.keep_lights = False
    settings.skip_empty = True
    settings.auto_cleanup_camera = True
    settings.camera_axis = "TOP"
    settings.padding_mode = "PIXELS"
    settings.padding_pixels = 0
    settings.pixels_per_unit = 16.0
    settings.resolution_multiple = 1
    settings.square_output = False
    settings.min_resolution = 1
    settings.max_resolution = 0
    settings.overwrite_policy = "SUFFIX"

    result = bpy.ops.bts.batch_export()
    check(result == {"FINISHED"}, "Collision export did not finish: %r" % (result,))
    files = sorted(os.listdir(out_dir))
    check(files == ["A_B.png", "A_B_2.png"], "Collision files: %r" % (files,))
    for name in files:
        os.remove(os.path.join(out_dir, name))
    os.rmdir(out_dir)


class _FakeOperator:
    pass


class _FakeLayout:
    def __getattr__(self, name):
        if name in (
            "use_property_split",
            "use_property_decorate",
            "alert",
            "enabled",
            "scale_y",
        ):
            return False

        def method(*args, **kwargs):
            if name == "operator":
                return _FakeOperator()
            return self

        return method


class _DrawHost:
    def __init__(self):
        self.layout = _FakeLayout()


def run_ui_draw_probe():
    """Call every panel draw path without a real UI layout."""
    from blender_to_sprites_batch_exporter import ui

    panels = (
        ui.BTS_PT_MainPanel,
        ui.BTS_PT_Source,
        ui.BTS_PT_Camera,
        ui.BTS_PT_Resolution,
        ui.BTS_PT_Output,
        ui.BTS_PT_Problems,
        ui.BTS_PT_Presets,
        ui.BTS_PT_Report,
    )
    for panel in panels:
        host = _DrawHost()
        for name in dir(panel):
            if name.startswith("_draw"):
                setattr(host, name, getattr(panel, name).__get__(host, panel))
        panel.draw(host, bpy.context)


def run_ui_icon_probe():
    """Every icon used by the panels must exist in this Blender version."""
    from blender_to_sprites_batch_exporter import ui

    with open(ui.__file__, encoding="utf-8") as handle:
        source = handle.read()
    icons = set(re.findall(r"icon=['\"]([A-Z0-9_]+)['\"]", source))
    parameter = bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"]
    valid = {item.identifier for item in parameter.enum_items}
    missing = sorted(icon for icon in icons if icon not in valid)
    check(not missing, "Unknown UI icons: %r" % (missing,))


def run_test():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon = load_addon()
    scene = bpy.context.scene
    view_layer = bpy.context.view_layer

    engine = set_engine(scene)
    scene.render.resolution_x = 32
    scene.render.resolution_y = 32
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = True

    col_a = make_collection("Body")
    col_b = make_collection("Weapon")
    col_empty = make_collection("EmptyCollection")
    col_lights = make_collection("Lights")

    add_cube(col_a, "BodyCube", location=(0.0, 0.0, 0.0), size=1.0)
    add_cube(col_b, "WeaponCube", location=(4.0, 0.0, 0.0), size=0.5)
    add_light(col_lights, "KeyLight")

    user_cam = add_camera(scene.collection, "MyCamera")
    scene.camera = user_cam
    user_cam_location = tuple(user_cam.location)
    user_cam_data_name = user_cam.data.name

    if os.environ.get("BTS_STRICT_CAMERA") == "1":
        # A user camera that happens to use the addon's internal name.
        # The add-on must not reuse or delete it.
        user_cam.name = TEMP_CAMERA_NAME
        user_cam_location = tuple(user_cam.location)
        user_cam_data_name = user_cam.data.name

    hidden_obj = add_cube(col_a, "HiddenCube", location=(0.0, 3.0, 0.0), size=0.5)
    hidden_obj.hide_render = True
    root_obj = add_root_object(scene)

    # These settings must not leak into rendered frames and must be restored.
    scene.render.use_border = True
    scene.render.use_crop_to_border = False
    scene.render.use_stamp = True
    scene.render.use_stamp_date = True

    out_dir = tempfile.mkdtemp(prefix="bts_smoke_")
    if not out_dir.endswith(os.sep):
        out_dir += os.sep

    settings = scene.bts_settings
    settings.output_dir = out_dir
    settings.file_format = "PNG"
    settings.color_mode = "RGBA"
    settings.color_depth = "8"
    settings.use_transparent = True
    settings.use_compositor_nodes = False
    settings.write_main_output = False
    settings.export_source = "ALL"
    settings.isolation_mode = "EXCLUDE"
    settings.keep_collections = ""
    settings.skip_empty = True
    settings.auto_cleanup_camera = True
    settings.camera_axis = "TOP"
    settings.padding_mode = "PIXELS"
    settings.padding_pixels = 4
    settings.pixels_per_unit = 32.0
    settings.resolution_multiple = 1
    settings.square_output = False
    settings.min_resolution = 1
    settings.max_resolution = 0
    settings.overwrite_policy = "OVERWRITE"

    initial_resolution = (
        scene.render.resolution_x,
        scene.render.resolution_y,
        scene.render.resolution_percentage,
    )
    initial_format = scene.render.image_settings.file_format
    initial_excludes = {
        path: lc.exclude
        for path, lc in addon.logic.iter_layer_collections(view_layer.layer_collection)
        if path
    }

    view_layer.update()
    result = bpy.ops.bts.batch_export()
    check(result == {"FINISHED"}, "Batch export did not finish: %r" % (result,))

    files = sorted(os.listdir(out_dir))
    check(files == ["Body.png", "Weapon.png"], "Unexpected files: %r" % (files,))

    check(scene.camera == user_cam, "Original scene camera was not restored")
    check(bpy.data.objects.get(user_cam.name) is not None, "User camera was deleted")
    check(tuple(user_cam.location) == user_cam_location, "User camera was moved")
    check(user_cam.data.name == user_cam_data_name, "User camera data was replaced")
    check("bts_owned_camera" not in user_cam, "User camera was marked as owned by add-on")

    current_resolution = (
        scene.render.resolution_x,
        scene.render.resolution_y,
        scene.render.resolution_percentage,
    )
    check(current_resolution == initial_resolution, "Render resolution was not restored")
    check(
        scene.render.image_settings.file_format == initial_format,
        "Image format was not restored",
    )
    check(hidden_obj.hide_render is True, "hide_render state was not restored")
    check(root_obj.hide_render is False, "Scene-root object hide_render was not restored")
    check(scene.render.use_border is True, "Render Border state was not restored")
    check(scene.render.use_crop_to_border is False, "Crop To Border state was not restored")
    check(scene.render.use_stamp is True, "Stamp state was not restored")
    check(scene.render.use_stamp_date is True, "Stamp Date state was not restored")

    # The add-on must remove its own temporary camera when auto cleanup is on.
    owned = [ob for ob in scene.objects if ob.type == "CAMERA" and ob.get("bts_owned_camera")]
    check(not owned, "Temporary camera was not removed: %r" % ([o.name for o in owned],))

    if initial_excludes:
        current_excludes = {
            path: lc.exclude
            for path, lc in addon.logic.iter_layer_collections(view_layer.layer_collection)
            if path
        }
        check(current_excludes == initial_excludes, "Collection exclude state was not restored")

    run_policy_checks(scene, settings, out_dir)

    # H1.3: with auto cleanup disabled the temporary camera stays, but the
    # original scene camera must still be restored.
    settings.auto_cleanup_camera = False
    result = bpy.ops.bts.batch_export()
    check(result == {"FINISHED"}, "Batch export with keep-camera did not finish: %r" % (result,))

    owned = [ob for ob in scene.objects if ob.type == "CAMERA" and ob.get("bts_owned_camera")]
    check(len(owned) == 1, "Temporary camera was not kept: %r" % ([o.name for o in owned],))
    check(scene.camera == user_cam, "Original scene camera was not restored with keep-camera")
    check(owned[0] != user_cam, "User camera was reused as temporary camera")
    if os.environ.get("BTS_STRICT_CAMERA") == "1":
        check(owned[0].name != user_cam.name, "Temporary camera name collides with user camera")

    result = bpy.ops.bts.cleanup()
    check(result == {"FINISHED"}, "Cleanup did not finish: %r" % (result,))
    owned = [ob for ob in scene.objects if ob.type == "CAMERA" and ob.get("bts_owned_camera")]
    check(not owned, "Cleanup did not remove the temporary camera: %r" % ([o.name for o in owned],))
    check(scene.camera == user_cam, "Cleanup changed the user scene camera")
    check(bpy.data.objects.get(user_cam.name) is not None, "Cleanup deleted the user camera")
    settings.auto_cleanup_camera = True

    run_collision_test()
    run_target_list_test()
    run_analysis_and_cancel_test()
    run_compositor_test()
    run_ui_draw_probe()
    run_ui_icon_probe()

    files = sorted(os.listdir(out_dir))
    print("SMOKE PASS")
    print("engine=%s" % engine)
    print("output=%s" % out_dir)
    print("files=%r" % (files,))
    if os.environ.get("BTS_KEEP_OUTPUT") != "1":
        # Keep the directory on failure, remove it on success.
        try:
            for name in os.listdir(out_dir):
                os.remove(os.path.join(out_dir, name))
            os.rmdir(out_dir)
        except OSError:
            pass
    return 0


def main():
    try:
        return run_test()
    except Exception:
        print("SMOKE FAIL")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
