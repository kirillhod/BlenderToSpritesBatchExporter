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
import shutil
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

    # A matching node format must not produce a mismatch warning.
    analysis, _ = logic.analyze_scene(bpy.context, settings, use_cache=False)
    check(
        len(settings.node_items) > 0,
        "File Output node list is empty",
    )
    check(
        all(item.name and item.detail for item in settings.node_items),
        "File Output node list rows are incomplete",
    )
    check(
        len(settings.preview_items) > 0,
        "Path Preview list is empty in node mode",
    )
    check(
        any(problem.code == "node_format_mismatch" for problem in analysis.problems),
        "EXR node with PNG selected must warn about the format",
    )
    original_media_type = active.format.media_type
    original_format = active.format.file_format
    active.format.media_type = "IMAGE"
    active.format.file_format = "PNG"
    analysis, _ = logic.analyze_scene(bpy.context, settings, use_cache=False)
    check(
        not any(
            problem.code == "node_format_mismatch"
            for problem in analysis.problems
        ),
        "Matching PNG node format must not warn",
    )
    active.format.media_type = original_media_type
    active.format.file_format = original_format
    logic.clear_analysis_cache(scene)

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

    # Single-layer image nodes append the socket name to node.file_name.
    single_dir = os.path.join(out_dir, "single")
    os.makedirs(single_dir, exist_ok=True)
    settings.output_dir = single_dir
    settings.node_naming = "PREFIX"
    active.format.media_type = "IMAGE"
    active.format.file_format = "PNG"
    result = bpy.ops.bts.batch_export()
    check(result == {"FINISHED"}, "Single-layer export did not finish: %r" % (result,))
    single_files = [
        name for name in os.listdir(single_dir) if name.lower().endswith(".png")
    ]
    check(
        single_files == ["Body_Sprite.png"],
        "Single-layer socket name was appended twice: %r" % (single_files,),
    )

    # An empty socket must not fall back to the node name or file name.
    empty_dir = os.path.join(out_dir, "empty")
    os.makedirs(empty_dir, exist_ok=True)
    settings.output_dir = empty_dir
    active.file_output_items[0].name = ""
    result = bpy.ops.bts.batch_export()
    check(result == {"FINISHED"}, "Empty-socket export did not finish: %r" % (result,))
    empty_files = [
        name for name in os.listdir(empty_dir) if name.lower().endswith(".png")
    ]
    check(
        empty_files == ["Body.png"],
        "Empty socket must use only the collection name: %r" % (empty_files,),
    )
    active.file_output_items[0].name = "Sprite"
    active.format.media_type = "MULTI_LAYER_IMAGE"
    active.format.file_format = "OPEN_EXR_MULTILAYER"
    settings.output_dir = prefix_dir
    logic.clear_analysis_cache(scene)

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
    body_item = next(
        item for item in settings.target_items if item.name == "Body"
    )
    check(
        re.fullmatch(r"\d+x\d+", body_item.size_status),
        "Row status is not a canvas size: %r" % (body_item.size_status,),
    )

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
    plan = next(
        task.output_plan
        for task in analysis.tasks
        if task.collection.name == "Body" and not task.skip_reason
    )
    check(
        plan.path.endswith("Body_sprite.png"),
        "Name template path: %r" % (plan.path,),
    )
    check(
        len(settings.preview_items) > 0,
        "Path Preview list is empty in main-output mode",
    )
    check(
        all(item.path for item in settings.preview_items),
        "Path Preview rows have no path",
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
    preset_rna = bpy.ops.bts.apply_preset.get_rna_type()
    preset_items = {
        item.identifier: item.description
        for item in preset_rna.properties["preset"].enum_items
    }
    check(
        set(preset_items) == set(logic.BUILTIN_PRESETS),
        "Preset enum identifiers: %r" % (sorted(preset_items),),
    )
    check(
        all(preset_items[name] for name in preset_items),
        "A preset enum item has no tooltip description",
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


def run_override_property_test():
    """Override toggles copy globals once and survive a .blend round trip."""
    from blender_to_sprites_batch_exporter import logic

    bpy.ops.wm.read_factory_settings(use_empty=True)
    load_addon()
    scene = bpy.context.scene
    set_engine(scene)
    body = make_collection("Body")
    add_cube(body, "BodyCube")

    out_dir = tempfile.mkdtemp(prefix="bts_overrides_")
    settings = scene.bts_settings
    settings.output_dir = out_dir
    settings.export_source = "ALL"
    settings.skip_empty = True
    settings.camera_margin = 30.0
    settings.padding_mode = "UNITS"
    settings.padding_pixels = 7
    settings.padding_units = 0.25
    settings.pixels_per_unit = 64.0
    settings.resolution_multiple = 8
    settings.square_output = True
    settings.min_resolution = 16
    settings.max_resolution = 512

    logic.rebuild_target_items(bpy.context, settings)
    item = next((row for row in settings.target_items if row.name == "Body"), None)
    check(item is not None, "Override test has no Body target")

    item.override_framing = True
    check(item.camera_margin == 30.0, "Framing margin was not copied")
    check(item.padding_mode == "UNITS", "Framing padding mode was not copied")
    check(item.padding_pixels == 7, "Framing pixel padding was not copied")
    check(item.padding_units == 0.25, "Framing unit padding was not copied")
    check(item.override_framing_seeded, "Framing override was not seeded")

    settings.camera_margin = 99.0
    check(
        item.camera_margin == 30.0,
        "Seeded framing override was overwritten by a global change",
    )

    item.override_framing = False
    check(not item.override_framing_seeded, "Framing seed was not cleared")
    item.override_framing = True
    check(
        item.camera_margin == 99.0,
        "Re-enabling Framing did not copy the current global values",
    )

    item.override_resolution = True
    check(item.pixels_per_unit == 64.0, "Resolution PPU was not copied")
    check(item.resolution_multiple == 8, "Resolution multiple was not copied")
    check(item.square_output, "Square output was not copied")
    check(item.min_resolution == 16, "Minimum resolution was not copied")
    check(item.max_resolution == 512, "Maximum resolution was not copied")
    check(item.override_resolution_seeded, "Resolution override was not seeded")

    before = logic.analysis_token(bpy.context, settings)
    item.padding_pixels = 9
    after = logic.analysis_token(bpy.context, settings)
    check(before != after, "Analysis token ignores target overrides")

    blend_path = os.path.join(out_dir, "overrides.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, check_existing=False)
    item.padding_pixels = 100
    item.override_resolution = False
    bpy.ops.wm.open_mainfile(filepath=blend_path, load_ui=False)

    scene = bpy.context.scene
    settings = scene.bts_settings
    item = next((row for row in settings.target_items if row.name == "Body"), None)
    check(item is not None, "Body target was lost after reload")
    check(item.override_framing, "Framing toggle was not saved")
    check(item.override_framing_seeded, "Framing seed was not saved")
    check(item.camera_margin == 99.0, "Framing value was not saved")
    check(item.override_resolution, "Resolution toggle was not saved")
    check(item.override_resolution_seeded, "Resolution seed was not saved")
    check(item.pixels_per_unit == 64.0, "Resolution PPU was not saved")
    check(item.padding_pixels == 9, "Framing padding was not saved")

    for name in os.listdir(out_dir):
        os.remove(os.path.join(out_dir, name))
    os.rmdir(out_dir)


def run_view_property_test():
    """Legacy axis migration, view overrides and the empty-view preflight."""
    from blender_to_sprites_batch_exporter import logic

    bpy.ops.wm.read_factory_settings(use_empty=True)
    load_addon()
    scene = bpy.context.scene
    set_engine(scene)
    body = make_collection("Body")
    add_cube(body, "BodyCube")

    settings = scene.bts_settings
    settings.export_source = "ALL"
    settings.skip_empty = True
    out_dir = tempfile.mkdtemp(prefix="bts_views_")
    settings.output_dir = out_dir

    for axis in logic.VIEW_AXES:
        logic.apply_view_migration(settings)
        settings.camera_axis = axis
        logic.apply_view_migration(settings)
        active = logic.active_view_axes(settings)
        check(active == [axis], "View migration for %s produced %r" % (axis, active))

    settings.views_migrated = True
    settings.view_top = True
    settings.view_front = True
    logic.migrate_settings(bpy.context, settings)
    check(
        settings.view_top and settings.view_front,
        "migrate_settings reset an already migrated multi-view set",
    )

    logic.rebuild_target_items(bpy.context, settings)
    item = next((row for row in settings.target_items if row.name == "Body"), None)
    check(item is not None, "View test has no Body target")

    settings.view_top = False
    settings.view_front = True
    settings.view_left = True
    item.override_view = True
    check(item.view_front, "View override did not copy Front")
    check(item.view_left, "View override did not copy Left")
    check(not item.view_top, "View override did not copy the disabled Top")
    check(item.override_view_seeded, "View override was not seeded")

    settings.view_back = True
    check(
        not item.view_back,
        "A seeded View override was overwritten by a global change",
    )
    check(
        logic.view_axes_for(settings, item) == ["FRONT", "LEFT"],
        "View override order is not canonical: %r"
        % (logic.view_axes_for(settings, item),),
    )

    item.view_front = False
    item.view_left = False
    check(
        logic.view_axes_for(settings, item) == [],
        "An empty View override did not stay empty",
    )
    analysis = logic.preflight(bpy.context, settings)
    problems = [
        problem
        for problem in analysis.problems
        if problem.code == "no_view" and problem.collection == "Body"
    ]
    check(problems, "Empty View override did not produce a no_view preflight error")

    item.view_top = True
    analysis = logic.preflight(bpy.context, settings)
    problems = [
        problem
        for problem in analysis.problems
        if problem.code == "no_view" and problem.collection == "Body"
    ]
    check(not problems, "A selected view still produced a no_view error")

    for name in os.listdir(out_dir):
        os.remove(os.path.join(out_dir, name))
    os.rmdir(out_dir)


def run_multi_view_export_test():
    """Four axes share one canvas and write four files, main and node mode."""
    from blender_to_sprites_batch_exporter import logic

    bpy.ops.wm.read_factory_settings(use_empty=True)
    load_addon()
    scene = bpy.context.scene
    set_engine(scene)
    body = make_collection("Body")
    cube = add_cube(body, "BodyCube")
    cube.scale = (1.0, 2.0, 3.0)

    out_dir = tempfile.mkdtemp(prefix="bts_views_export_")
    settings = scene.bts_settings
    settings.output_dir = out_dir
    settings.file_format = "PNG"
    settings.color_mode = "RGBA"
    settings.color_depth = "8"
    settings.use_transparent = True
    settings.use_compositor_nodes = False
    settings.export_source = "ALL"
    settings.isolation_mode = "EXCLUDE"
    settings.keep_lights = False
    settings.keep_collections = ""
    settings.skip_empty = True
    settings.overwrite_policy = "OVERWRITE"
    settings.camera_axis = "TOP"
    settings.camera_margin = 10.0
    settings.padding_mode = "PIXELS"
    settings.padding_pixels = 0
    settings.padding_units = 0.0
    settings.pixels_per_unit = 16.0
    settings.resolution_multiple = 1
    settings.square_output = False
    settings.min_resolution = 1
    settings.max_resolution = 0
    settings.views_migrated = True
    settings.view_top = False
    settings.view_bottom = False
    settings.view_front = True
    settings.view_back = True
    settings.view_right = True
    settings.view_left = True

    logic.rebuild_target_items(bpy.context, settings)
    analysis, _ = logic.analyze_scene(bpy.context, settings, use_cache=False)
    check(not analysis.errors, "Multi-view analysis: %r" % (analysis.problems,))

    target = next(item for item in analysis.targets if item.name == "Body")
    check(
        target.axes == ("FRONT", "BACK", "RIGHT", "LEFT"),
        "Multi-view axes: %r" % (target.axes,),
    )
    check(
        target.frame.res_x == 32 and target.frame.res_y == 48,
        "Multi-view shared canvas: %r" % (target.frame,),
    )
    body_item = next(
        item for item in settings.target_items if item.name == "Body"
    )
    check(
        body_item.size_status == "32x48, 4 views",
        "Multi-view row status: %r" % (body_item.size_status,),
    )
    check(len(analysis.tasks) == 4, "Multi-view task count: %r" % (len(analysis.tasks),))
    check(
        all(task.canvas is target.frame for task in analysis.tasks),
        "Multi-view tasks do not share the collection canvas",
    )
    expected = ["Body_front", "Body_back", "Body_right", "Body_left"]
    check(
        sorted(plan.collection for plan in analysis.main_plans) == sorted(expected),
        "Multi-view plan names: %r"
        % ([plan.collection for plan in analysis.main_plans],),
    )

    result = bpy.ops.bts.batch_export()
    check(result == {"FINISHED"}, "Multi-view export: %r" % (result,))
    for name in expected:
        path = os.path.join(out_dir, name + ".png")
        check(os.path.exists(path), "Missing multi-view file: %s" % path)
        check(
            image_size(path) == (32, 48),
            "Multi-view size for %s: %r" % (name, image_size(path)),
        )
    check(
        all("[" in line for line in settings.last_report.splitlines() if "Body" in line and ":" in line),
        "Multi-view report does not show axes: %r" % (settings.last_report,),
    )

    # Node mode: every axis gets its own collection subfolder.
    tree = bpy.data.node_groups.new("BTS Multi View", "CompositorNodeTree")
    scene.compositing_node_group = tree
    tree.interface.new_socket(
        name="Image", in_out="OUTPUT", socket_type="NodeSocketColor"
    )
    render_layers = tree.nodes.new("CompositorNodeRLayers")
    group_output = tree.nodes.new("NodeGroupOutput")
    active = tree.nodes.new("CompositorNodeOutputFile")
    active.name = "Active Output"
    active.directory = out_dir
    active.file_output_items.new("RGBA", "Sprite")
    tree.links.new(render_layers.outputs["Image"], group_output.inputs["Image"])
    tree.links.new(render_layers.outputs["Image"], active.inputs["Sprite"])

    settings.use_compositor_nodes = True
    settings.nodes_connected_only = True
    settings.node_naming = "SUBFOLDER"
    settings.node_override_base = True
    settings.write_main_output = False

    analysis, _ = logic.analyze_scene(bpy.context, settings, use_cache=False)
    check(not analysis.errors, "Multi-view node analysis: %r" % (analysis.problems,))
    node_names = sorted(
        os.path.basename(os.path.dirname(plan.path))
        for plan in analysis.node_plans
    )
    check(
        node_names == sorted(expected),
        "Multi-view node folders: %r" % (node_names,),
    )

    result = bpy.ops.bts.batch_export()
    check(result == {"FINISHED"}, "Multi-view node export: %r" % (result,))
    for name in expected:
        path = os.path.join(out_dir, name, "Sprite.exr")
        check(os.path.exists(path), "Missing node output: %s" % path)

    shutil.rmtree(out_dir)


def image_size(path):
    image = bpy.data.images.load(path, check_existing=False)
    try:
        return tuple(image.size)
    finally:
        bpy.data.images.remove(image)


def run_override_export_test():
    """Per-collection framing and resolution reach the render loop."""
    from blender_to_sprites_batch_exporter import logic

    bpy.ops.wm.read_factory_settings(use_empty=True)
    load_addon()
    scene = bpy.context.scene
    set_engine(scene)
    body = make_collection("Body")
    weapon = make_collection("Weapon")
    add_cube(body, "BodyCube")
    add_cube(weapon, "WeaponCube")

    out_dir = tempfile.mkdtemp(prefix="bts_override_export_")
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
    settings.camera_margin = 10.0
    settings.padding_mode = "PIXELS"
    settings.padding_pixels = 0
    settings.padding_units = 0.0
    settings.pixels_per_unit = 16.0
    settings.resolution_multiple = 1
    settings.square_output = False
    settings.min_resolution = 1
    settings.max_resolution = 0

    logic.rebuild_target_items(bpy.context, settings)
    body_item = next(item for item in settings.target_items if item.name == "Body")
    weapon_item = next(
        item for item in settings.target_items if item.name == "Weapon"
    )
    body_item.override_framing = True
    body_item.padding_pixels = 8
    body_item.override_resolution = True
    body_item.pixels_per_unit = 32.0

    analysis, _ = logic.analyze_scene(bpy.context, settings, use_cache=False)
    check(not analysis.errors, "Override analysis: %r" % (analysis.problems,))
    body_target = next(target for target in analysis.targets if target.name == "Body")
    weapon_target = next(
        target for target in analysis.targets if target.name == "Weapon"
    )
    check(
        body_target.override_groups == ("framing", "resolution"),
        "Active override groups: %r" % (body_target.override_groups,),
    )
    check(
        body_target.frame.res_x == 48 and body_target.frame.res_y == 48,
        "Body override frame: %r" % (body_target.frame,),
    )
    check(
        weapon_target.frame.res_x == 16 and weapon_target.frame.res_y == 16,
        "Weapon global frame: %r" % (weapon_target.frame,),
    )

    result = bpy.ops.bts.batch_export()
    check(result == {"FINISHED"}, "Override export: %r" % (result,))
    body_path = next(
        task.output_plan.path
        for task in analysis.tasks
        if task.collection.name == "Body" and not task.skip_reason
    )
    weapon_path = next(
        task.output_plan.path
        for task in analysis.tasks
        if task.collection.name == "Weapon" and not task.skip_reason
    )
    check(image_size(body_path) == (48, 48), "Body output size: %r" % (image_size(body_path),))
    check(
        image_size(weapon_path) == (16, 16),
        "Weapon output size: %r" % (image_size(weapon_path),),
    )
    check(
        "Body: overrides framing, resolution" in settings.last_report,
        "Override report is missing: %r" % (settings.last_report,),
    )

    body_item.override_framing = False
    body_item.override_resolution = False
    analysis, _ = logic.analyze_scene(bpy.context, settings, use_cache=False)
    body_target = next(target for target in analysis.targets if target.name == "Body")
    check(
        body_target.override_groups == (),
        "Disabled override groups: %r" % (body_target.override_groups,),
    )
    check(
        body_target.frame.res_x == 16 and body_target.frame.res_y == 16,
        "No-override frame: %r" % (body_target.frame,),
    )

    result = bpy.ops.bts.batch_export()
    check(result == {"FINISHED"}, "No-override export: %r" % (result,))
    check(
        image_size(body_path) == (16, 16),
        "No-override output size: %r" % (image_size(body_path),),
    )

    for name in os.listdir(out_dir):
        os.remove(os.path.join(out_dir, name))
    os.rmdir(out_dir)


def run_override_ui_test():
    """The override box follows the visible active target row."""
    from blender_to_sprites_batch_exporter import logic, ui

    bpy.ops.wm.read_factory_settings(use_empty=True)
    load_addon()
    scene = bpy.context.scene
    set_engine(scene)
    body = make_collection("Body")
    weapon = make_collection("Weapon")
    add_cube(body, "BodyCube")
    add_cube(weapon, "WeaponCube", location=(4.0, 0.0, 0.0), size=0.5)

    settings = scene.bts_settings
    settings.export_source = "ALL"
    settings.skip_empty = True
    logic.rebuild_target_items(bpy.context, settings)
    items = list(settings.target_items)
    body_index = next(i for i, item in enumerate(items) if item.name == "Body")
    weapon_index = next(i for i, item in enumerate(items) if item.name == "Weapon")

    settings.active_target_index = body_index
    item = ui._active_target_item(bpy.context, settings)
    check(item is not None and item.name == "Body", "Override box active row")
    item.override_view = True
    item.override_framing = True
    item.override_resolution = True
    ui._draw_overrides(_DrawHost().layout, item)
    item.override_view = False
    item.override_framing = False
    item.override_resolution = False

    settings.active_target_index = weapon_index
    item = ui._active_target_item(bpy.context, settings)
    check(item is not None and item.name == "Weapon", "Override box row change")

    settings.target_search = "Body"
    check(
        ui._active_target_item(bpy.context, settings) is None,
        "Override box ignored the target search",
    )
    settings.target_search = ""

    body_layer = logic.find_layer_collection(bpy.context.view_layer, "Body")
    bpy.context.view_layer.active_layer_collection = body_layer
    logic.set_active_target_index(settings, weapon_index)
    settings.export_source = "ACTIVE"
    active = ui._active_target_item(bpy.context, settings)
    check(
        active is None,
        "Override box ignored the export-mode filter: item=%r sources=%r"
        % (
            getattr(active, "name", None),
            [
                collection.name
                for collection in logic.gather_source_collections(
                    bpy.context, settings
                )
            ],
        ),
    )


def run_list_density_test():
    """List rows follow 0/2/50 collections and the search filter."""
    from blender_to_sprites_batch_exporter import logic, ui

    bpy.ops.wm.read_factory_settings(use_empty=True)
    load_addon()
    scene = bpy.context.scene
    set_engine(scene)
    settings = scene.bts_settings
    settings.export_source = "ALL"
    settings.target_search = ""
    logic.rebuild_target_items(bpy.context, settings)
    check(
        ui._target_row_count(bpy.context, settings) == 0,
        "Empty scene target rows: %r"
        % (ui._target_row_count(bpy.context, settings),),
    )

    body = make_collection("Body")
    weapon = make_collection("Weapon")
    add_cube(body, "BodyCube")
    add_cube(weapon, "WeaponCube")
    logic.rebuild_target_items(bpy.context, settings)
    check(
        ui._target_row_count(bpy.context, settings) == 2,
        "Two-collection target rows: %r"
        % (ui._target_row_count(bpy.context, settings),),
    )
    check(ui._list_rows(2, 3, 8) == 3, "Two targets should use three rows")

    for index in range(48):
        make_collection("Filler%02d" % index)
    logic.rebuild_target_items(bpy.context, settings)
    check(
        ui._target_row_count(bpy.context, settings) == 50,
        "Fifty-collection target rows: %r"
        % (ui._target_row_count(bpy.context, settings),),
    )
    check(ui._list_rows(50, 3, 8) == 8, "Fifty targets should cap at eight rows")

    settings.target_search = "Body"
    check(
        ui._target_row_count(bpy.context, settings) == 1,
        "Search did not reduce target rows",
    )
    check(ui._list_rows(1, 3, 8) == 3, "One target should still use three rows")
    settings.target_search = ""

    check(ui._list_rows(0, 1, 3) == 1, "Empty Always Include should use one row")
    check(ui._list_rows(0, 1, 4) == 1, "Empty Path Preview should use one row")
    check(ui._list_rows(4, 1, 4) == 4, "Four preview files should use four rows")


def run_collision_test():
    """Collections that sanitize to the same name block the export."""
    from blender_to_sprites_batch_exporter import logic

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

    analysis, _ = logic.analyze_scene(bpy.context, settings, use_cache=False)
    check(
        any(problem.code == "name_collision" for problem in analysis.problems),
        "Sanitized name collision was not reported: %r"
        % (analysis.problems,),
    )

    try:
        result = bpy.ops.bts.batch_export()
    except RuntimeError as exc:
        check(
            "name_collision" in str(exc),
            "Collision export raised an unexpected error: %s" % exc,
        )
    else:
        check(
            result == {"CANCELLED"},
            "Collision export should be blocked: %r" % (result,),
        )
    check(
        not os.listdir(out_dir),
        "Collision export wrote files: %r" % (sorted(os.listdir(out_dir)),),
    )
    os.rmdir(out_dir)


def run_target_sync_test():
    """Auto-sync keeps flags, overrides and the active row by name."""
    from blender_to_sprites_batch_exporter import logic

    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon = load_addon()
    scene = bpy.context.scene
    set_engine(scene)
    body = make_collection("Body")
    weapon = make_collection("Weapon")
    add_cube(body, "BodyCube")
    add_cube(weapon, "WeaponCube", location=(4.0, 0.0, 0.0), size=0.5)

    settings = scene.bts_settings
    settings.export_source = "ALL"
    settings.skip_empty = True
    logic.migrate_settings(bpy.context, settings)
    names = [item.name for item in settings.target_items]
    check("Body" in names and "Weapon" in names, "Sync seed list: %r" % (names,))

    body_item = next(item for item in settings.target_items if item.name == "Body")
    weapon_item = next(item for item in settings.target_items if item.name == "Weapon")
    body_item.enabled = False
    settings.active_target_index = list(settings.target_items).index(weapon_item)

    extra = make_collection("Extra")
    add_cube(extra, "ExtraCube", location=(8.0, 0.0, 0.0), size=0.5)
    logic.sync_depsgraph_handler(
        bpy.context.scene, bpy.context.evaluated_depsgraph_get()
    )
    logic.apply_pending_target_sync()
    names = [item.name for item in settings.target_items]
    check("Extra" in names, "Auto-sync did not add a collection: %r" % (names,))
    body_item = next(item for item in settings.target_items if item.name == "Body")
    check(body_item.enabled is False, "Auto-sync lost the disabled flag")
    active = settings.active_target_index
    check(
        0 <= active < len(settings.target_items)
        and settings.target_items[active].name == "Weapon",
        "Auto-sync did not preserve the active row",
    )

    bpy.data.collections.remove(extra)
    logic.sync_depsgraph_handler(
        bpy.context.scene, bpy.context.evaluated_depsgraph_get()
    )
    logic.apply_pending_target_sync()
    names = [item.name for item in settings.target_items]
    check("Extra" not in names, "Auto-sync did not drop a deleted collection: %r" % (names,))

    body_item.size_status = "512x304"
    logic.clear_analysis_cache(scene)
    check(
        all(not item.size_status for item in settings.target_items),
        "Clearing the analysis did not clear row statuses",
    )

    logic.push_target_sync_suppression()
    check(
        logic.request_target_sync(bpy.context) is False,
        "Sync was requested while suppressed",
    )
    logic.pop_target_sync_suppression()
    logic.unregister_target_sync()


def run_target_filter_test():
    """export_source filters targets and the Outliner selection is mutual."""
    from blender_to_sprites_batch_exporter import logic, ui

    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon = load_addon()
    scene = bpy.context.scene
    set_engine(scene)
    body = make_collection("Body")
    weapon = make_collection("Weapon")
    extra = make_collection("Extra")
    add_cube(body, "BodyCube")
    add_cube(weapon, "WeaponCube", location=(4.0, 0.0, 0.0), size=0.5)
    add_cube(extra, "ExtraCube", location=(8.0, 0.0, 0.0), size=0.5)

    settings = scene.bts_settings
    settings.output_dir = tempfile.mkdtemp(prefix="bts_filter_")
    settings.export_source = "ALL"
    settings.skip_empty = True
    settings.use_compositor_nodes = False
    logic.migrate_settings(bpy.context, settings)
    logic.sync_target_items(bpy.context, settings)

    names = [item.name for item in settings.target_items]
    check(names == ["Body", "Weapon", "Extra"], "Initial target registry: %r" % (names,))

    def set_active(name):
        layer = logic.find_layer_collection(bpy.context.view_layer, name)
        check(layer is not None, "Layer collection not found: %s" % name)
        bpy.context.view_layer.active_layer_collection = layer

    def flush_sync():
        logic.sync_depsgraph_handler(scene)
        logic.apply_pending_target_sync()
        logic.sync_target_items(bpy.context, settings)

    def active_name():
        index = int(settings.active_target_index)
        return settings.target_items[index].name

    set_active("Body")
    flush_sync()
    check(active_name() == "Body", "Outliner selection did not set the active row")

    settings.export_source = "ACTIVE"
    flush_sync()
    check(
        [c.name for c in logic.gather_target_collections(bpy.context, settings)]
        == ["Body"],
        "ACTIVE mode exported more than the active collection",
    )
    ulist = ui.BTS_UL_Targets
    class _FilterFlags:
        bitflag_filter_item = 1
    flags, _order = ulist.filter_items(
        _FilterFlags(), bpy.context, settings, "target_items"
    )
    visible = [
        item.name
        for item, flag in zip(settings.target_items, flags)
        if flag
    ]
    check(visible == ["Body"], "ACTIVE filter shows: %r" % (visible,))
    check(
        len(settings.target_items) == 3,
        "The filter discarded the persistent target registry",
    )

    set_active("Weapon")
    flush_sync()
    check(active_name() == "Weapon", "New Outliner selection did not activate its row")
    check(
        [c.name for c in logic.gather_target_collections(bpy.context, settings)]
        == ["Weapon"],
        "ACTIVE mode did not follow the new Outliner collection",
    )

    extra_item = next(item for item in settings.target_items if item.name == "Extra")
    extra_item.enabled = False
    settings.export_source = "ALL"
    flush_sync()
    exported = sorted(c.name for c in logic.gather_target_collections(bpy.context, settings))
    check(exported == ["Body", "Weapon"], "ALL filter export: %r" % (exported,))
    check(extra_item.enabled is False, "Disabled flag was lost after mode switches")

    weapon_index = list(settings.target_items).index(
        next(item for item in settings.target_items if item.name == "Weapon")
    )
    settings.active_target_index = weapon_index
    check(
        bpy.context.view_layer.active_layer_collection.collection.name == "Weapon",
        "Selecting a target row did not select it in the Outliner",
    )
    logic.unregister_target_sync()


class _FakeOperator:
    pass


class _FakeLayout:
    def panel(self, *args, **kwargs):
        return self, self

    def panel_prop(self, *args, **kwargs):
        return self, self

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
    run_list_density_test()
    run_override_property_test()
    run_view_property_test()
    run_multi_view_export_test()
    run_override_export_test()
    run_override_ui_test()
    run_target_sync_test()
    run_target_filter_test()
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
