bl_info = {
    "name": "Blender To Sprites Batch Exporter",
    "author": "kirillhod",
    "version": (1, 4, 0),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar (N) > Batch Export",
    "description": "Batch render collections to sprites with an auto-fitted orthographic camera.",
    "category": "Import-Export",
}

import bpy
from bpy.props import PointerProperty

from . import logic
from .logic import clear_analysis_cache
from .properties import BTS_Settings
from .operators import (
    BTS_OT_Analyze,
    BTS_OT_BatchExport,
    BTS_OT_CancelExport,
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
    BTS_OT_Analyze,
    BTS_OT_CancelExport,
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


def _clear_cache_on_load(*_args):
    clear_analysis_cache()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bts_settings = PointerProperty(type=BTS_Settings)
    handlers = bpy.app.handlers.load_post
    if _clear_cache_on_load not in handlers:
        handlers.append(_clear_cache_on_load)


def unregister():
    if hasattr(bpy.types.Scene, "bts_settings"):
        del bpy.types.Scene.bts_settings
    handlers = bpy.app.handlers.load_post
    if _clear_cache_on_load in handlers:
        handlers.remove(_clear_cache_on_load)
    clear_analysis_cache()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
