"""Property definitions for the add-on.

Keep property names, defaults and enum identifiers unchanged: scenes store
these values under ``scene.bts_settings``.
"""

from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup


class BTS_Settings(PropertyGroup):
    output_dir: StringProperty(name="Output Directory", description="Folder for rendered sprites", default="//sprites/", subtype='DIR_PATH')
    file_format: EnumProperty(name="Format", items=[('PNG', "PNG", ""), ('JPEG', "JPEG", ""), ('OPEN_EXR', "EXR", ""), ('TIFF', "TIFF", ""), ('WEBP', "WebP", ""), ('TARGA', "Targa", ""), ('BMP', "BMP", "")], default='PNG')
    color_mode: EnumProperty(name="Color", items=[('BW', "BW", ""), ('RGB', "RGB", ""), ('RGBA', "RGBA", "")], default='RGBA')
    color_depth: EnumProperty(name="Depth", items=[('8', "8", ""), ('16', "16", ""), ('32', "32", "")], default='8')
    use_transparent: BoolProperty(name="Transparent Film", default=True)
    use_compositor_nodes: BoolProperty(name="Use File Output Nodes", description="Let File Output nodes write the files", default=True)

    node_naming: EnumProperty(
        name="Collection Goes To",
        description="How the collection name is applied to File Output nodes",
        items=[
            ('SUBFOLDER', "Subfolder", "base/<Collection>/"),
            ('PREFIX', "Filename Prefix", "base/<Collection>_<file>"),
            ('NONE', "Don't Modify", "Leave node paths alone"),
        ],
        default='SUBFOLDER',
    )

    node_override_base: BoolProperty(name="Override Base Paths", description="Replace each node's base path with the Output Directory.", default=False)
    write_main_output: BoolProperty(name="Also Write Main Render", description="Also save the Render Result to the Output Directory", default=False)
    nodes_connected_only: BoolProperty(name="Only Connected Nodes", description="Use only File Output nodes connected to the compositor output; disconnected nodes never write files", default=True)
    use_prefix_fallback: BoolProperty(name="Emergency Prefix Rename", description="Rename files after rendering if a File Output node could not be modified. May break external .meta files", default=False)

    overwrite_policy: EnumProperty(
        name="Overwrite",
        description="What to do when an output file already exists",
        items=[
            ('ASK', "Ask", "Ask before overwriting existing files"),
            ('ERROR', "Error", "Stop the export when a file exists"),
            ('SKIP', "Skip", "Skip collections whose files already exist"),
            ('OVERWRITE', "Overwrite", "Overwrite existing files"),
            ('SUFFIX', "Add Suffix", "Write name_2, name_3, ... instead of overwriting"),
        ],
        default='ASK',
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
    export_source: EnumProperty(name="Export", items=[('ALL', "All Collections", ""), ('INCLUDED', "Only Included", ""), ('ACTIVE', "Active Collection", ""), ('TOPLEVEL', "Top-Level Only", "")], default='ALL')
    skip_empty: BoolProperty(name="Skip Empty Collections", description="Skip collections without renderable geometry", default=True)
