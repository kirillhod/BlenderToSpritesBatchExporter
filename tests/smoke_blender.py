"""Blender smoke test for Blender To Sprites Batch Exporter.

Run:
    blender -b --factory-startup --python tests/smoke_blender.py

Optional environment variables:
    BTS_REPO             Path to repository root (defaults to parent of tests/).
    BTS_STRICT_CAMERA=1  Also test a user camera named like the temporary one.
    BTS_KEEP_OUTPUT=1    Keep rendered files for inspection.
"""

import os
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

    print("SMOKE PASS")
    print("engine=%s" % engine)
    print("output=%s" % out_dir)
    print("files=%r" % (files,))
    if os.environ.get("BTS_KEEP_OUTPUT") != "1":
        # Keep the directory on failure, remove it on success.
        try:
            for name in files:
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
