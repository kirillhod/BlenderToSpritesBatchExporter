bl_info = {
    "name": "Blender To Sprites Batch Exporter",
    "author": "kirillhod",
    "version": (2, 0, 1),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar (N) > Batch Export",
    "description": "Batch render collections to sprites with an auto-fitted orthographic camera.",
    "category": "Import-Export",
}

import bpy
from bpy.props import PointerProperty

from . import logic
from .logic import clear_analysis_cache, migrate_settings
from .properties import BTS_CollectionRef, BTS_Settings, BTS_TargetItem
from .operators import (
    BTS_OT_ActivateTarget,
    BTS_OT_AddAlwaysInclude,
    BTS_OT_Analyze,
    BTS_OT_ApplyPreset,
    BTS_OT_BatchExport,
    BTS_OT_CancelExport,
    BTS_OT_Cleanup,
    BTS_OT_CopyReport,
    BTS_OT_LoadPreset,
    BTS_OT_OpenLog,
    BTS_OT_OpenOutputFolder,
    BTS_OT_PreviewCamera,
    BTS_OT_RefreshTargets,
    BTS_OT_RemoveAlwaysInclude,
    BTS_OT_RestoreCollections,
    BTS_OT_SavePreset,
    BTS_OT_TargetsActive,
    BTS_OT_TargetsAll,
    BTS_OT_TargetsNone,
)
from .ui import (
    BTS_PT_Camera,
    BTS_PT_MainPanel,
    BTS_PT_Output,
    BTS_PT_Presets,
    BTS_PT_Problems,
    BTS_PT_Report,
    BTS_PT_Resolution,
    BTS_PT_Source,
    BTS_UL_AlwaysInclude,
    BTS_UL_Targets,
)

classes = (
    BTS_TargetItem,
    BTS_CollectionRef,
    BTS_Settings,
    BTS_UL_Targets,
    BTS_UL_AlwaysInclude,
    BTS_OT_BatchExport,
    BTS_OT_Analyze,
    BTS_OT_CancelExport,
    BTS_OT_RefreshTargets,
    BTS_OT_TargetsAll,
    BTS_OT_TargetsNone,
    BTS_OT_TargetsActive,
    BTS_OT_ActivateTarget,
    BTS_OT_AddAlwaysInclude,
    BTS_OT_RemoveAlwaysInclude,
    BTS_OT_CopyReport,
    BTS_OT_OpenLog,
    BTS_OT_ApplyPreset,
    BTS_OT_SavePreset,
    BTS_OT_LoadPreset,
    BTS_OT_PreviewCamera,
    BTS_OT_Cleanup,
    BTS_OT_RestoreCollections,
    BTS_OT_OpenOutputFolder,
    BTS_PT_MainPanel,
    BTS_PT_Source,
    BTS_PT_Camera,
    BTS_PT_Resolution,
    BTS_PT_Output,
    BTS_PT_Problems,
    BTS_PT_Presets,
    BTS_PT_Report,
)


def _clear_cache_on_load(*_args):
    clear_analysis_cache()
    try:
        scene = bpy.context.scene
        settings = getattr(scene, "bts_settings", None)
        if settings is not None:
            migrate_settings(bpy.context, settings)
    except Exception:
        pass


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
