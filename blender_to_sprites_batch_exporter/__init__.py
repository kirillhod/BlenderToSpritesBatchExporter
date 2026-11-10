bl_info = {
    "name": "Blender To Sprites Batch Exporter",
    "author": "kirillhod",
    "version": (1, 3, 1),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar (N) > Batch Export",
    "description": "Batch render collections to sprites with an auto-fitted orthographic camera.",
    "category": "Import-Export",
}

import bpy
from bpy.props import PointerProperty

from . import logic
from .properties import BTS_Settings
from .operators import (
    BTS_OT_BatchExport,
    BTS_OT_Cleanup,
    BTS_OT_OpenOutputFolder,
    BTS_OT_PreviewCamera,
    BTS_OT_RestoreCollections,
)
from .ui import (
    BTS_PT_Camera,
    BTS_PT_MainPanel,
    BTS_PT_Output,
    BTS_PT_Resolution,
    BTS_PT_Source,
)

classes = (
    BTS_Settings,
    BTS_OT_BatchExport,
    BTS_OT_PreviewCamera,
    BTS_OT_Cleanup,
    BTS_OT_RestoreCollections,
    BTS_OT_OpenOutputFolder,
    BTS_PT_MainPanel,
    BTS_PT_Source,
    BTS_PT_Camera,
    BTS_PT_Resolution,
    BTS_PT_Output,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bts_settings = PointerProperty(type=BTS_Settings)


def unregister():
    if hasattr(bpy.types.Scene, "bts_settings"):
        del bpy.types.Scene.bts_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
