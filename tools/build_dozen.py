"""A dozen fish, each in three colourways and two wildcards, as a sheet and as GLBs for the fishbowl.

    blender --background --python tools/build_dozen.py -- --mode sheet [--samples 64]
    blender --background --python tools/build_dozen.py -- --mode export

sheet   renders art/pinata/fishdraw/dozen.png (+ dozen.json for tools/label_sheet.py dozen)
export  writes bowl/fish/<seed>_<variant>.glb (+ .glb.txt, base64, which bowl/index.html loads) and bowl/fish/index.json
"""
import base64
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import build_pinata_fish as F  # noqa: E402

K = F.K
SEEDS = [7, 11, 19, 31, 58, 77, 123, 404, 777, 1234, 2024, 9001]
TRAITS = ["twin tail", "giant eyes", "fluffy", "crown", "long fins", "chubby"]
BOWL = K.ROOT / "bowl" / "fish"


def versions():
    """Per fish: three palettes (the first is its own) and two wildcards on the first palette,
    one single trait and one stacked pair, so across the dozen every trait turns up several times."""
    out = []
    for i, seed in enumerate(SEEDS):
        rng = random.Random(seed * 31)
        pals = [i % 6] + rng.sample([p for p in range(6) if p != i % 6], 2)
        solo = (TRAITS[i % 6],)
        pair = tuple(rng.sample([t for t in TRAITS if t != solo[0]], 2))
        rows = [(seed, i, f"colour {'ABC'[k]}", (), p) for k, p in enumerate(pals)]
        rows += [(seed, i, "wild 1", solo, pals[0]), (seed, i, "wild 2", pair, pals[0])]
        out.append(rows)
    return out


def sheet(samples):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = K.scene_setup(samples)
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.86, 0.92, 1.0, 1)
    cells = [c for rows in versions() for c in rows]
    cols, dx, dz = 5, 6.0, 3.9
    rows = math.ceil(len(cells) / cols)
    placed = []
    for i, (seed, index, variant, wild, pal) in enumerate(cells):
        origin = Vector(((i % cols - (cols - 1) / 2) * dx, 0, -(i // cols) * dz))
        name, _ = F.build(seed, index, origin, "common", wild, pal_index=pal)
        label = f"{name}" if variant == "colour A" else ("Wildcard: " + " + ".join(wild) if wild else variant[0].upper() + variant[1:])
        placed.append((label, origin))
        print("built", seed, variant, wild, flush=True)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=80)
    back = K.new_object("Backdrop", bm)
    back.rotation_euler = (math.pi / 2, 0, 0)
    back.location = (0, 2.4, 0)
    back.data.materials.append(K.flat_material("Backdrop", (0.80, 0.76, 0.66), 0.95))
    width, height = cols * dx + 0.8, rows * dz + 0.6
    cz = -(rows - 1) * dz / 2 - 0.3
    res = (2600, round(2600 * height / width))
    from bpy_extras.object_utils import world_to_camera_view
    K.shoot(scene, "dozen", (0, -60, cz), (0, 0, cz), ortho=max(width, height), res=res)   # ortho scale spans the longer side
    marks = []
    for label, origin in placed:
        v = world_to_camera_view(scene, scene.camera, origin + Vector((0, -0.6, -1.6)))
        marks.append([label, round(v.x * res[0], 1), round((1 - v.y) * res[1], 1)])
    (F.DATA / "dozen.json").write_text(json.dumps({"size": list(res), "cells": marks}, indent=1))


def export():
    BOWL.mkdir(parents=True, exist_ok=True)
    listing = []
    for rows in versions():
        entry = None
        for seed, index, variant, wild, pal in rows:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            name, style = F.build(seed, index, Vector((0, 0, 0)), "common", wild, pal_index=pal)
            # the paper colours live in "Col"; unless it is the active colour layer the exporter writes a blank COLOR_0
            for me in bpy.data.meshes:
                if "Col" in me.color_attributes:
                    me.color_attributes.active_color = me.color_attributes["Col"]
                    me.color_attributes.render_color_index = me.color_attributes.find("Col")
            file = f"{seed}_{variant.replace(' ', '')}.glb"
            kw = dict(filepath=str(BOWL / file), export_format="GLB", export_draco_mesh_compression_enable=True,
                      export_draco_mesh_compression_level=7, export_yup=True)
            try:
                bpy.ops.export_scene.gltf(**kw, export_vertex_color="ACTIVE")
            except TypeError:
                bpy.ops.export_scene.gltf(**kw)
            if entry is None:
                entry = {"seed": seed, "name": name, "eyes": style, "versions": []}
            entry["versions"].append({"file": file, "label": "Wildcard: " + " + ".join(wild) if wild else variant[0].upper() + variant[1:]})
            # the bowl page loads base64 text: Claude artifacts and some static hosts do not serve .glb
            (BOWL / f"{file}.txt").write_text(base64.b64encode((BOWL / file).read_bytes()).decode())
            print("exported", file, flush=True)
        listing.append(entry)
    (BOWL / "index.json").write_text(json.dumps(listing, indent=1))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    mode = argv[argv.index("--mode") + 1] if "--mode" in argv else "sheet"
    samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 64
    sheet(samples) if mode == "sheet" else export()


if __name__ == "__main__":
    main()
