"""Property definitions for the add-on.

Keep existing property names and enum identifiers: scenes store these values
under ``scene.bts_settings``. New 2.0.0 fields have safe defaults and are
migrated once per scene.
"""

from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup


def _invalidate_analysis(_self, context):
    try:
        from .logic import clear_analysis_cache
        clear_analysis_cache(context.scene)
    except Exception:
        pass


def _active_target_changed(_self, context):
    """Mirror the active target row in the Outliner, unless sync set it."""
    try:
        from .logic import active_target_update_suppressed, find_layer_collection
        if active_target_update_suppressed():
            return
        index = int(getattr(_self, "active_target_index", 0))
        if not 0 <= index < len(_self.target_items):
            return
        name = _self.target_items[index].name
        view_layer = getattr(context, "view_layer", None)
        if view_layer is None:
            return
        layer = find_layer_collection(view_layer, name)
        if layer is not None and view_layer.active_layer_collection != layer:
            view_layer.active_layer_collection = layer
    except Exception:
        pass


def _export_source_changed(_self, context):
    """Clear preflight and rebuild the visible target list for the new mode."""
    _invalidate_analysis(_self, context)
    try:
        from .logic import request_target_sync
        request_target_sync(context)
    except Exception:
        pass


class BTS_TargetItem(PropertyGroup):
    """One collection selected for export."""

    name: StringProperty(name="Collection")
    enabled: BoolProperty(name="Export", default=True, update=_invalidate_analysis)
    size_status: StringProperty(name="Status", default="")


class BTS_CollectionRef(PropertyGroup):
    """Reference to a collection that is always included."""

    name: StringProperty(name="Collection")


class BTS_PreviewItem(PropertyGroup):
    """One planned output file in the Path Preview list."""

    name: StringProperty(name="Collection")
    path: StringProperty(name="Path")
    exists: BoolProperty(name="Exists", default=False)


class BTS_NodeItem(PropertyGroup):
    """One File Output node in the compact node list."""

    name: StringProperty(name="Node")
    detail: StringProperty(name="Details")


class BTS_Settings(PropertyGroup):
    target_items: CollectionProperty(type=BTS_TargetItem)
    always_include_items: CollectionProperty(type=BTS_CollectionRef)
    preview_items: CollectionProperty(type=BTS_PreviewItem)
    node_items: CollectionProperty(type=BTS_NodeItem)
    target_items_migrated: BoolProperty(default=False, options={'HIDDEN'})
    always_include_migrated: BoolProperty(default=False, options={'HIDDEN'})
    layout_migrated: BoolProperty(default=False, options={'HIDDEN'})
    target_search: StringProperty(
        name="Filter",
        description="Show only target rows whose collection name contains this text",
        default="",
    )
    active_target_index: IntProperty(
        default=0,
        min=0,
        update=_active_target_changed,
    )
    active_include_index: IntProperty(default=0, min=0)
    active_preview_index: IntProperty(default=0, min=0)
    active_node_index: IntProperty(default=0, min=0)
    show_path_preview: BoolProperty(
        name="Path Preview",
        description="Show the planned output files in a compact list",
        default=True,
    )
    name_template: StringProperty(
        name="Name Template",
        description=(
            "File name template for the main render. {collection} is replaced "
            "by the collection name. Default: {collection}. Examples: "
            "{collection} writes Body.png; {collection}_sprite writes "
            "Body_sprite.png"
        ),
        default="{collection}",
        update=_invalidate_analysis,
    )
    last_report: StringProperty(default="", options={'HIDDEN'})
    last_log_path: StringProperty(default="", subtype='FILE_PATH', options={'HIDDEN'})
    preset_description: StringProperty(
        name="Preset Description",
        description="Description stored with a custom JSON preset",
        default="",
    )
    debug_log: BoolProperty(name="Debug Log", default=False)

    output_dir: StringProperty(
        name="Output Directory",
        description=(
            "Folder for rendered sprites. A path starting with // is relative "
            "to the saved .blend file; save the file before exporting"
        ),
        default="//sprites/",
        subtype='DIR_PATH',
    )
    file_format: EnumProperty(
        name="Format",
        description="Image format for the main render",
        items=[
            ('PNG', "PNG", "Lossless image with alpha support"),
            ('JPEG', "JPEG", "Compact image without alpha"),
            ('OPEN_EXR', "EXR", "High dynamic range image"),
            ('TIFF', "TIFF", "Lossless image with alpha support"),
            ('WEBP', "WebP", "Compact image with optional alpha"),
            ('TARGA', "Targa", "Legacy image with alpha support"),
            ('BMP', "BMP", "Uncompressed image without alpha"),
        ],
        default='PNG',
    )
    color_mode: EnumProperty(
        name="Color",
        description="Color channels stored in the main render",
        items=[
            ('BW', "BW", "Grayscale, single channel"),
            ('RGB', "RGB", "Color without transparency"),
            ('RGBA', "RGBA", "Color with transparency"),
        ],
        default='RGBA',
    )
    color_depth: EnumProperty(
        name="Depth",
        description="Bits per color channel for formats that support a choice",
        items=[
            ('8', "8", "8 bits per channel"),
            ('16', "16", "16 bits per channel"),
            ('32', "32", "32 bits per channel"),
        ],
        default='8',
    )
    use_transparent: BoolProperty(
        name="Transparent Film",
        description="Write transparent pixels instead of the world background",
        default=True,
    )
    use_compositor_nodes: BoolProperty(
        name="Use File Output Nodes",
        description=(
            "Let connected File Output nodes write the files. When disabled, "
            "the compositor is turned off during export"
        ),
        default=True,
    )

    node_naming: EnumProperty(
        name="Node Output Layout",
        description=(
            "Where the collection identity is placed in File Output paths. "
            "Automatic picks a safe layout; the other modes set the folder or "
            "file prefix explicitly"
        ),
        items=[
            ('AUTO', "Automatic",
             "Write <Collection>_<socket name>.exr for every File Output node"),
            ('FILENAME', "Collection Only",
             "Write <Collection>.exr; ignores socket names and requires one node"),
            ('SUBFOLDER', "Collection Folder",
             "Write <Collection>/<socket name>.exr"),
            ('PREFIX', "Collection + Socket",
             "Write <Collection>_<socket name>.exr"),
            ('NONE', "Don't Modify (manual)",
             "Leave node paths alone; only safe for one collection"),
        ],
        default='AUTO',
    )

    node_override_base: BoolProperty(
        name="Override Node Base Paths",
        description=(
            "Replace every File Output node base path with the Output "
            "Directory. When off, node paths stay unchanged"
        ),
        default=False,
    )
    write_main_output: BoolProperty(
        name="Also Save Main Render",
        description=(
            "Save the Render Result in addition to File Output files. Required "
            "for the add-on Format, Color and Depth settings to take effect in "
            "node mode, and to write PNG or JPEG from File Output nodes"
        ),
        default=False,
    )
    nodes_connected_only: BoolProperty(
        name="Only Connected Nodes",
        description=(
            "Use only File Output nodes connected to the compositor output; "
            "disconnected nodes never write files"
        ),
        default=True,
    )

    overwrite_policy: EnumProperty(
        name="Overwrite",
        description="What to do when an output file already exists",
        items=[
            ('OVERWRITE', "Overwrite", "Replace existing files (recommended)"),
            ('ASK', "Ask", "Ask before overwriting existing files"),
            ('ERROR', "Error", "Stop the export when a file exists"),
            ('SKIP', "Skip", "Skip collections whose files already exist"),
            ('SUFFIX', "Add Suffix", "Write name_2, name_3, ... instead of overwriting"),
        ],
        default='OVERWRITE',
    )

    camera_axis: EnumProperty(
        name="View Axis",
        description=(
            "Direction the camera looks from for a single-view export. "
            "Default: Top"
        ),
        items=[
            ('TOP', "Top", "Look down -Z"),
            ('BOTTOM', "Bottom", "Look up +Z"),
            ('FRONT', "Front", "Look along +Y"),
            ('BACK', "Back", "Look along -Y"),
            ('RIGHT', "Right", "Look along -X"),
            ('LEFT', "Left", "Look along +X"),
        ],
        default='TOP',
    )
    camera_margin: FloatProperty(
        name="Camera Distance Margin",
        description=(
            "Extra distance between the camera and the collection bounds. "
            "Keeps geometry away from the camera clipping plane. Default: 10"
        ),
        default=10.0,
        min=0.01,
        soft_max=1000.0,
    )
    auto_cleanup_camera: BoolProperty(
        name="Remove Camera After Export",
        description="Delete the temporary camera after the export finishes",
        default=True,
    )

    padding_mode: EnumProperty(
        name="Padding Mode",
        description="Measure the empty border around the sprite in pixels or world units",
        items=[
            ('PIXELS', "Pixels", "Padding is a number of output pixels"),
            ('UNITS', "Units", "Padding is a distance in Blender units"),
        ],
        default='PIXELS',
    )
    padding_pixels: IntProperty(
        name="Padding",
        description="Empty border in output pixels around the collection. Default: 16",
        default=16,
        min=0,
        soft_max=512,
    )
    padding_units: FloatProperty(
        name="Padding",
        description="Empty border in Blender units around the collection. Default: 0.1",
        default=0.1,
        min=0.0,
        soft_max=100.0,
    )

    pixels_per_unit: FloatProperty(
        name="Pixels / Unit",
        description=(
            "Output pixels per Blender unit. Higher values produce larger, "
            "more detailed sprites. Default: 100"
        ),
        default=100.0,
        min=0.001,
        soft_max=2048.0,
    )
    resolution_multiple: IntProperty(
        name="Round To Multiple Of",
        description=(
            "Round width and height up to a multiple of this value. "
            "1 disables rounding. Default: 1"
        ),
        default=1,
        min=1,
        soft_max=64,
    )
    square_output: BoolProperty(
        name="Square Output",
        description="Force the same width and height for every sprite",
        default=False,
    )
    min_resolution: IntProperty(
        name="Min Res",
        description="Minimum width and height in pixels. Default: 1",
        default=1,
        min=1,
        soft_max=8192,
    )
    max_resolution: IntProperty(
        name="Max Res",
        description="Maximum width and height in pixels. 0 means unlimited. Default: 0",
        default=0,
        min=0,
        soft_max=16384,
    )

    isolation_mode: EnumProperty(
        name="Isolation",
        description="How other collections are hidden while a target is rendered",
        items=[
            ('EXCLUDE', "Exclude Collections", "Temporarily exclude other collections from the view layer"),
            ('HIDE', "Disable in Renders", "Temporarily disable other objects in renders"),
        ],
        default='EXCLUDE',
    )
    keep_collections: StringProperty(name="Always Include", description="Comma-separated collection names that stay visible", default="")
    keep_lights: BoolProperty(
        name="Always Keep Lights",
        description=(
            "Keep collections that contain lights so the render stays lit. "
            "Other objects in those collections may appear in the render"
        ),
        default=True,
    )
    export_source: EnumProperty(
        name="Export",
        description="Which collections seed the target list: all collections, only included ones, the active collection, or top-level collections only",
        items=[
            ('ALL', "All Collections", "Offer every collection in the scene"),
            ('INCLUDED', "Only Included", "Offer only collections that are not excluded from the view layer"),
            ('ACTIVE', "Active Collection", "Offer only the active collection"),
            ('TOPLEVEL', "Top-Level Only", "Offer only collections directly under the scene collection"),
        ],
        default='ALL',
        update=_export_source_changed,
    )
    skip_empty: BoolProperty(
        name="Skip Empty Collections",
        description="Skip collections without renderable geometry",
        default=True,
    )
