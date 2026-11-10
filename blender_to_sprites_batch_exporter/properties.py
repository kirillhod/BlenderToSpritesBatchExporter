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


class BTS_TargetItem(PropertyGroup):
    """One collection selected for export."""

    name: StringProperty(name="Collection")
    enabled: BoolProperty(name="Export", default=True, update=_invalidate_analysis)
    size_status: StringProperty(name="Status", default="")


class BTS_CollectionRef(PropertyGroup):
    """Reference to a collection that is always included."""

    name: StringProperty(name="Collection")


class BTS_Settings(PropertyGroup):
    target_items: CollectionProperty(type=BTS_TargetItem)
    always_include_items: CollectionProperty(type=BTS_CollectionRef)
    target_items_migrated: BoolProperty(default=False, options={'HIDDEN'})
    always_include_migrated: BoolProperty(default=False, options={'HIDDEN'})
    layout_migrated: BoolProperty(default=False, options={'HIDDEN'})
    target_search: StringProperty(name="Filter", default="")
    active_target_index: IntProperty(default=0, min=0)
    active_include_index: IntProperty(default=0, min=0)
    name_template: StringProperty(
        name="Name Template",
        description=(
            "Name for the main render. Use {collection}; for example "
            "{collection} or {collection}_sprite"
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

    output_dir: StringProperty(name="Output Directory", description="Folder for rendered sprites", default="//sprites/", subtype='DIR_PATH')
    file_format: EnumProperty(name="Format", items=[('PNG', "PNG", ""), ('JPEG', "JPEG", ""), ('OPEN_EXR', "EXR", ""), ('TIFF', "TIFF", ""), ('WEBP', "WebP", ""), ('TARGA', "Targa", ""), ('BMP', "BMP", "")], default='PNG')
    color_mode: EnumProperty(name="Color", items=[('BW', "BW", ""), ('RGB', "RGB", ""), ('RGBA', "RGBA", "")], default='RGBA')
    color_depth: EnumProperty(name="Depth", items=[('8', "8", ""), ('16', "16", ""), ('32', "32", "")], default='8')
    use_transparent: BoolProperty(name="Transparent Film", default=True)
    use_compositor_nodes: BoolProperty(name="Use File Output Nodes", description="Let File Output nodes write the files", default=True)

    node_naming: EnumProperty(
        name="Node Output Layout",
        description="Where the collection identity is placed in File Output paths",
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
        description="Replace every File Output node base path with the Output Directory",
        default=False,
    )
    write_main_output: BoolProperty(
        name="Also Save Main Render",
        description="Save the Render Result in addition to File Output files",
        default=False,
    )
    nodes_connected_only: BoolProperty(name="Only Connected Nodes", description="Use only File Output nodes connected to the compositor output; disconnected nodes never write files", default=True)

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

    camera_axis: EnumProperty(name="View Axis", items=[('TOP', "Top", "Look down -Z"), ('BOTTOM', "Bottom", "Look up +Z"), ('FRONT', "Front", "Look along +Y"), ('BACK', "Back", "Look along -Y"), ('RIGHT', "Right", "Look along -X"), ('LEFT', "Left", "Look along +X")], default='TOP')
    camera_margin: FloatProperty(name="Camera Distance Margin", description="Extra distance between camera and bounds", default=10.0, min=0.01, soft_max=1000.0)
    auto_cleanup_camera: BoolProperty(name="Remove Camera After Export", default=True)

    padding_mode: EnumProperty(name="Padding Mode", items=[('PIXELS', "Pixels", ""), ('UNITS', "Units", "")], default='PIXELS')
    padding_pixels: IntProperty(name="Padding", default=16, min=0, soft_max=512)
    padding_units: FloatProperty(name="Padding", default=0.1, min=0.0, soft_max=100.0)

    pixels_per_unit: FloatProperty(name="Pixels / Unit", default=100.0, min=0.001, soft_max=2048.0)
    resolution_multiple: IntProperty(name="Round To Multiple Of", default=1, min=1, soft_max=64)
    square_output: BoolProperty(name="Square Output", default=False)
    min_resolution: IntProperty(name="Min Res", default=1, min=1, soft_max=8192)
    max_resolution: IntProperty(name="Max Res", description="0 = unlimited", default=0, min=0, soft_max=16384)

    isolation_mode: EnumProperty(name="Isolation", items=[('EXCLUDE', "Exclude Collections", ""), ('HIDE', "Disable in Renders", "")], default='EXCLUDE')
    keep_collections: StringProperty(name="Always Include", description="Comma-separated collection names that stay visible", default="")
    keep_lights: BoolProperty(name="Always Keep Lights", default=True)
    export_source: EnumProperty(name="Export", items=[('ALL', "All Collections", ""), ('INCLUDED', "Only Included", ""), ('ACTIVE', "Active Collection", ""), ('TOPLEVEL', "Top-Level Only", "")], default='ALL', update=_invalidate_analysis)
    skip_empty: BoolProperty(name="Skip Empty Collections", description="Skip collections without renderable geometry", default=True)
