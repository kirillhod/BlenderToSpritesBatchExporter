"""Minimal bpy/mathutils stubs for running pure-logic unit tests outside Blender.

Only the small surface needed by :mod:`blender_to_sprites_batch_exporter.logic`
is implemented. These stubs are never imported by the Blender smoke test.
"""

import sys
import types


class Vector:
    def __init__(self, values):
        self.values = list(values)

    def __getitem__(self, index):
        return self.values[index]

    def __setitem__(self, index, value):
        self.values[index] = value

    def __len__(self):
        return len(self.values)

    def __iter__(self):
        return iter(self.values)

    def __add__(self, other):
        return Vector(a + b for a, b in zip(self.values, other.values))

    def __sub__(self, other):
        return Vector(a - b for a, b in zip(self.values, other.values))

    def __mul__(self, scalar):
        return Vector(v * scalar for v in self.values)

    __rmul__ = __mul__

    def __truediv__(self, scalar):
        return Vector(v / scalar for v in self.values)

    def copy(self):
        return Vector(self.values)

    def __repr__(self):
        return f"Vector({self.values!r})"


class Euler:
    def __init__(self, values):
        self.values = list(values)

    def __repr__(self):
        return f"Euler({self.values!r})"


def install():
    existing = sys.modules.get("bpy")
    if existing is not None and getattr(existing, "_bts_stub", False):
        return

    bpy = types.ModuleType("bpy")
    bpy._bts_stub = True
    bpy_props = types.ModuleType("bpy.props")
    bpy_types = types.ModuleType("bpy.types")
    bpy_utils = types.ModuleType("bpy.utils")

    def dummy_prop(*args, **kwargs):
        return None

    for name in (
        "StringProperty",
        "FloatProperty",
        "IntProperty",
        "BoolProperty",
        "EnumProperty",
        "PointerProperty",
    ):
        setattr(bpy_props, name, dummy_prop)

    class DummyBase:
        pass

    for name in ("Operator", "Panel", "PropertyGroup"):
        setattr(bpy_types, name, type(name, (DummyBase,), {}))

    bpy_types.Scene = type("Scene", (DummyBase,), {})
    bpy_utils.register_class = lambda cls: None
    bpy_utils.unregister_class = lambda cls: None

    bpy.props = bpy_props
    bpy.types = bpy_types
    bpy.utils = bpy_utils
    bpy.data = types.SimpleNamespace(is_saved=True)
    bpy.path = types.SimpleNamespace(abspath=lambda path: path)

    mathutils = types.ModuleType("mathutils")
    mathutils.Vector = Vector
    mathutils.Euler = Euler

    sys.modules["bpy"] = bpy
    sys.modules["bpy.props"] = bpy_props
    sys.modules["bpy.types"] = bpy_types
    sys.modules["bpy.utils"] = bpy_utils
    sys.modules["mathutils"] = mathutils
