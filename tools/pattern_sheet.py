"""Sheets for judging the piñata shape and the coat patterns.

    blender --background --python tools/pattern_sheet.py -- shapes  [seeds...]   # fishdraw vs piñata shape vs piñata + pattern
    blender --background --python tools/pattern_sheet.py -- patterns [seed]      # every base, accent and face on one fish
    blender --background --python tools/pattern_sheet.py -- recipes [seeds...]   # each seed's own recipe on the piñata shape
    python tools/label_sheet.py <shapes|patterns|recipes>

Writes art/pinata/fishdraw/<mode>.png and <mode>.json (labels for tools/label_sheet.py).
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import build_pinata_fish as F  # noqa: E402

K, P = F.K, F.P
DOZEN = [7, 11, 19, 31, 58, 77, 123, 404, 777, 1234, 2024, 9001]


def sheet(name, cells, cols, view=(0.42, -1, 0.3), dx=6.4, dz=4.4, samples=48):
    """cells: (label, build kwargs). One render, labels written beside it."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = K.scene_setup(samples)
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.86, 0.92, 1.0, 1)
    rows = math.ceil(len(cells) / cols)
    placed = []
    for i, (label, kw) in enumerate(cells):
        origin = Vector(((i % cols - (cols - 1) / 2) * dx, 0, -(i // cols) * dz))
        F.build(origin=origin, **kw)
        placed.append((label, origin))
        print("built", label, flush=True)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=90)
    back = K.new_object("Backdrop", bm)
    back.rotation_euler = (math.pi / 2, 0, 0)
    back.location = (0, 3.2, 0)
    back.data.materials.append(K.flat_material("Backdrop", (0.80, 0.76, 0.66), 0.95))
    width, height = cols * dx + 0.8, rows * dz + 0.6
    cz = -(rows - 1) * dz / 2 - 0.3
    res = (2400, round(2400 * height / width))
    d = Vector(view).normalized()
    K.shoot(scene, name, tuple(Vector((0, 0, cz)) + d * 70), (0, 0, cz), ortho=max(width, height) * 1.06, res=res)
    from bpy_extras.object_utils import world_to_camera_view
    marks = []
    for label, origin in placed:
        v = world_to_camera_view(scene, scene.camera, origin + Vector((0, -0.6, -1.8)))
        marks.append([label, round(v.x * res[0], 1), round((1 - v.y) * res[1], 1)])
    (F.DATA / f"{name}.json").write_text(json.dumps({"size": list(res), "cells": marks}, indent=1))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    mode, nums = (argv[0] if argv else "patterns"), [int(a) for a in argv[1:]]
    if mode == "shapes":
        cells = []
        for i, seed in enumerate(nums or [7, 31, 58, 404, 1234, 2024]):
            base = dict(seed=seed, index=i)
            cells += [(f"{seed}: fishdraw", base), (f"{seed}: piñata shape", dict(base, form="pinata")),
                      (f"{seed}: + pattern", dict(base, form="pinata", coat="auto"))]
        sheet("shapes", cells, 3, view=(0, -1, 0.12))
    elif mode == "patterns":
        seed = nums[0] if nums else 404
        base = dict(seed=seed, index=1, form="pinata")
        cells = [(f"base: {b}", dict(base, coat=P.Recipe(b, (), "plain", seed=3))) for b in P.BASES]
        cells += [(f"accent: {a}", dict(base, coat=P.Recipe("plain", [a], "plain", seed=5))) for a in P.ACCENTS]
        cells += [(f"face: {f}", dict(base, coat=P.Recipe("cape", (), f, seed=8, base_p={"level": 0.25, "waves": 2.6, "phase": 1, "stitch": True})))
                  for f in P.FACES]
        sheet("patterns", cells, 6, view=(0, -1, 0.15))
    else:
        cells = []
        for i, seed in enumerate(nums or DOZEN):
            recipe = P.Recipe.from_seed(seed)
            cells.append((f"{seed}: {recipe.describe()}", dict(seed=seed, index=i, form="pinata", coat=recipe)))
        sheet("recipes", cells, 4, view=(0, -1, 0.15))


if __name__ == "__main__":
    main()
