bl_info = {
    "name": "Blender To Sprites Batch Exporter",
    "author": "kirillhod",
    "version": (3, 2, 3),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar (N) > Batch Export",
    "description": "Batch render collections to sprites with an auto-fitted orthographic camera.",
    "category": "Import-Export",
}

import bpy
from bpy.props import PointerProperty

from . import logic
from .logic import (
    clear_analysis_cache,
    clear_previews,
    exit_all_previews,
    migrate_settings,
    preview_depsgraph_handler,
    request_target_sync,
    sync_depsgraph_handler,
    unregister_target_sync,
)
from .properties import (
    BTS_CollectionRef,
    BTS_NodeItem,
    BTS_PreviewItem,
    BTS_Settings,
    BTS_TargetItem,
)
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
    BTS_UL_NodeOutputs,
    BTS_UL_Preview,
    BTS_UL_Targets,
)

classes = (
    BTS_TargetItem,
    BTS_CollectionRef,
    BTS_PreviewItem,
    BTS_NodeItem,
    BTS_Settings,
    BTS_UL_Targets,
    BTS_UL_AlwaysInclude,
    BTS_UL_Preview,
    BTS_UL_NodeOutputs,
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
    clear_previews()
    try:
        scene = bpy.context.scene
        settings = getattr(scene, "bts_settings", None)
        if settings is not None:
            migrate_settings(bpy.context, settings)
    except Exception:
        pass
    try:
        request_target_sync(bpy.context)
    except Exception:
        pass


def _restore_preview_on_save(*_args):
    try:
        exit_all_previews()
    except Exception:
        pass


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bts_settings = PointerProperty(type=BTS_Settings)
    handlers = bpy.app.handlers.load_post
    if _clear_cache_on_load not in handlers:
        handlers.append(_clear_cache_on_load)
    depsgraph_handlers = bpy.app.handlers.depsgraph_update_post
    if sync_depsgraph_handler not in depsgraph_handlers:
        depsgraph_handlers.append(sync_depsgraph_handler)
    if preview_depsgraph_handler not in depsgraph_handlers:
        depsgraph_handlers.append(preview_depsgraph_handler)
    save_handlers = bpy.app.handlers.save_pre
    if _restore_preview_on_save not in save_handlers:
        save_handlers.append(_restore_preview_on_save)
    try:
        from .core.canvas_grid import register_canvas_grid
        register_canvas_grid()
    except Exception:  # noqa: BLE001 - the grid is a viewport extra
        pass


def unregister():
    try:
        from .core.canvas_grid import unregister_canvas_grid
        unregister_canvas_grid()
    except Exception:  # noqa: BLE001
        pass
    try:
        exit_all_previews()
    except Exception:
        pass
    if hasattr(bpy.types.Scene, "bts_settings"):
        del bpy.types.Scene.bts_settings
    handlers = bpy.app.handlers.load_post
    if _clear_cache_on_load in handlers:
        handlers.remove(_clear_cache_on_load)
    depsgraph_handlers = bpy.app.handlers.depsgraph_update_post
    if sync_depsgraph_handler in depsgraph_handlers:
        depsgraph_handlers.remove(sync_depsgraph_handler)
    if preview_depsgraph_handler in depsgraph_handlers:
        depsgraph_handlers.remove(preview_depsgraph_handler)
    save_handlers = bpy.app.handlers.save_pre
    if _restore_preview_on_save in save_handlers:
        save_handlers.remove(_restore_preview_on_save)
    unregister_target_sync()
    clear_analysis_cache()
    clear_previews()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
