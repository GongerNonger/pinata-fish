"""Paper piñata fish from fishdraw shapes, with colour variants, rare variants and wildcards.

    node tools/fishdraw_export.mjs 11 2024 404 9001
    blender --background --python tools/build_pinata_fish.py -- 11 2024 404 9001 [--samples 96] [--out variants]

Each seed is one base design: its side silhouette, fin outlines and eye come from
art/pinata/fishdraw/fish_<seed>.json, and its face (eye style, whiskers, crest) is chosen from the seed.
For every design the sheet shows four versions side by side:
    common          the design in its own colours
    colour variant  the same fish in another palette
    rare            golden, midnight, albino or rainbow
    wildcard        the common fish with two odd traits (twin tail, giant eyes, fluffy, crown, long fins, chubby)
Writes art/pinata/fishdraw/<out>.png and <out>.json (the label for each cell and where it sits).
"""
import colorsys
import json
import math
import os
import random
import sys
from pathlib import Path

os.environ["PIN_STAGE"] = "3"            # from the koi script we want the body, fringe and motifs only
os.environ["PIN_OUT"] = "fishdraw"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import build_pinata_koi as K  # noqa: E402

DATA = K.ROOT / "art" / "pinata" / "fishdraw"
LENGTH = 3.6
NOSE = 0.14                              # the front of the head is rebuilt as a rounded cap up to here
BASE_ROWS, BASE_W, BASE_LEN = K.ROWS, 0.11, 0.36
COLOUR_AT = K.colour_at

# body (two shades), marking (two shades), and the three accents that go with them
PALETTES = [
    dict(body=[(1.0, 0.965, 0.90), (1.0, 0.91, 0.80)], mark=[(1.0, 0.27, 0.10), (1.0, 0.46, 0.08)], gold=(1.0, 0.76, 0.16), teal=(0.08, 0.70, 0.68), deep=(0.70, 0.07, 0.12)),
    dict(body=[(0.16, 0.74, 0.86), (0.10, 0.62, 0.80)], mark=[(1.0, 0.86, 0.20), (1.0, 0.72, 0.12)], gold=(1.0, 0.36, 0.52), teal=(1.0, 1.0, 0.95), deep=(0.10, 0.25, 0.55)),
    dict(body=[(0.62, 0.36, 0.86), (0.52, 0.28, 0.78)], mark=[(1.0, 0.62, 0.14), (1.0, 0.78, 0.22)], gold=(0.20, 0.86, 0.78), teal=(1.0, 0.96, 0.86), deep=(0.30, 0.10, 0.48)),
    dict(body=[(1.0, 0.42, 0.62), (0.98, 0.32, 0.52)], mark=[(1.0, 0.97, 0.90), (1.0, 0.90, 0.80)], gold=(1.0, 0.80, 0.18), teal=(0.20, 0.72, 0.90), deep=(0.72, 0.10, 0.34)),
    dict(body=[(0.55, 0.86, 0.22), (0.44, 0.78, 0.18)], mark=[(1.0, 0.95, 0.80), (0.98, 0.88, 0.62)], gold=(1.0, 0.45, 0.12), teal=(0.95, 0.20, 0.50), deep=(0.12, 0.42, 0.20)),
    dict(body=[(1.0, 0.70, 0.12), (1.0, 0.58, 0.08)], mark=[(0.16, 0.16, 0.20), (0.26, 0.24, 0.30)], gold=(1.0, 0.98, 0.90), teal=(0.10, 0.70, 0.66), deep=(0.72, 0.26, 0.04)),
]
RARES = {
    "golden": dict(body=[(1.0, 0.80, 0.22), (1.0, 0.68, 0.10)], mark=[(1.0, 0.97, 0.82), (1.0, 0.90, 0.62)], gold=(1.0, 0.45, 0.10), teal=(1.0, 1.0, 0.92), deep=(0.75, 0.38, 0.05)),
    "midnight": dict(body=[(0.09, 0.10, 0.22), (0.14, 0.13, 0.30)], mark=[(1.0, 0.20, 0.62), (0.20, 0.90, 0.95)], gold=(1.0, 0.85, 0.20), teal=(0.30, 1.0, 0.80), deep=(0.45, 0.20, 0.80)),
    "albino": dict(body=[(1.0, 0.98, 0.95), (1.0, 0.93, 0.90)], mark=[(1.0, 0.80, 0.84), (1.0, 0.70, 0.76)], gold=(1.0, 0.60, 0.70), teal=(0.96, 0.86, 0.90), deep=(0.92, 0.32, 0.42)),
    "rainbow": None,                     # keeps the design's palette; every row of fringe takes the next hue
}
RARE_ORDER = ["golden", "midnight", "albino", "rainbow"]
WILD_ORDER = [("twin tail", "giant eyes"), ("fluffy", "crown"), ("long fins", "chubby"), ("crown", "twin tail")]
EYE_STYLES = ["round", "sleepy", "beady", "wide", "lashes", "grumpy"]


class Markings:
    """Seeded patches in body space (t along, v across), standing in for a painted coat strip."""
    def __init__(self, rng):
        self.blobs = [(rng.uniform(0.2, 0.9), rng.uniform(0.2, 0.8), rng.uniform(0.08, 0.2), rng.uniform(0.15, 0.4)) for _ in range(rng.randint(2, 5))]
        self.bands = rng.random() < 0.35
        self.period = rng.uniform(0.16, 0.3)

    def is_marked(self, t, v):
        if self.bands:
            return (t / self.period) % 1 < 0.42
        return any(((t - bt) / rt) ** 2 + ((v - bv) / rv) ** 2 < 1 for bt, bv, rt, rv in self.blobs)


class Shape:
    def __init__(self, data):
        self.cols = list(data["cols"])
        for i in range(len(self.cols)):                       # fill any gap with its neighbour
            if self.cols[i] is None:
                self.cols[i] = next(c for c in self.cols[i:] + self.cols[:i][::-1] if c)
        self.hmax = max((c["top"] - c["bot"]) / 2 for c in self.cols)

    def raw(self, t):
        x = min(max(t, 0.0), 1.0) * (len(self.cols) - 1)
        i = min(int(x), len(self.cols) - 2)
        f = x - i
        a, b = self.cols[i], self.cols[i + 1]
        top, bot = a["top"] + (b["top"] - a["top"]) * f, a["bot"] + (b["bot"] - a["bot"]) * f
        return (top + bot) / 2, max(0.004, (top - bot) / 2)

    def at(self, t):
        """Mid-line height and half-height at t. fishdraw's jaw comes to a point; here the head ends in a
        round cap instead, which is the difference between a snout and a face."""
        if t >= NOSE:
            return self.raw(t)
        mid0, h0 = self.raw(NOSE)
        mid, _ = self.raw(t)
        u = 1 - t / NOSE
        return mid0 + (mid - mid0) * 0.3, max(0.004, h0 * math.sqrt(max(0.0, 1 - u * u)))


def install(shape, pal, fat=1.0, fluffy=False):
    """Point the koi script's shape and colour hooks at this fish."""
    def frame(t):
        mid, _ = shape.at(t)
        mid2, _ = shape.at(t + 0.01)
        c = Vector((LENGTH / 2 - t * LENGTH, 0, mid * LENGTH))
        d = Vector((-0.01 * LENGTH, 0, (mid2 - mid) * LENGTH)).normalized()
        return c, d, Vector((0, -1, 0)), Vector((0, 0, 1))

    def radii(t):
        _, h = shape.at(t)
        tail = min(1.0, math.sqrt(max(0.02, (1 - t) / 0.07)))        # round off the tail stock
        h = max(0.03, h * LENGTH * tail) * fat
        return max(0.03, min(h * 0.8, 0.22 * LENGTH * fat)), h

    K.L, K.frame, K.radii = LENGTH, frame, radii
    K.HALF = shape.hmax * LENGTH * 0.8
    K.profile = lambda t: shape.at(t)[1] / shape.hmax
    K.WHITE, K.RED = pal["body"], pal["mark"]
    K.GOLD, K.TEAL, K.CRIMSON = pal["gold"], pal["teal"], pal["deep"]
    K.BELLY = tuple(min(1.0, c * 0.6 + 0.42) for c in pal["body"][0])
    K.ROWS = BASE_ROWS
    K.STRIP_W, K.STRIP_LEN = (0.13, 0.64) if fluffy else (BASE_W, BASE_LEN)


def streamer_fin(bm, col, shape, poly, pal, side=0, splay=0.0, reach=1.0, shift=0):
    """A fin as a fan of paper streamers, the way the body is fringe. Every streamer runs from where the fin
    joins the body out to fishdraw's fin outline, so the fan keeps that fin's shape, and all of them sweep back
    toward the tail as a real fin's rays do.

    side = 0 is a fin on the mid-line (dorsal, anal, tail): its streamers are rooted along the fin's base,
    each one ahead of its own tip. side = -1 / +1 is a paired fin on a flank: fishdraw draws those over the
    body, so the whole fan is rooted at the outline's front corner and leans outward by `splay`."""
    def inside(t, z):
        mid, h = shape.at(min(max(t, 0), 1))
        return abs(z - mid) < h * 0.92

    stripes = [pal["mark"][0], pal["body"][0], pal["gold"], pal["body"][1], pal["mark"][1], pal["deep"]]
    if side:
        front = min(poly, key=lambda p: p[0])
        tips = [p for p in poly if p[0] - front[0] > 0.02]
        base_lo = base_hi = front[0]
    else:
        tips = [p for p in poly if not inside(*p)]
        inner = [p for p in poly if inside(*p)]
        if inner:
            base_lo, base_hi = min(p[0] for p in inner), max(p[0] for p in inner)
        elif tips:
            base_lo = base_hi = min(tips, key=lambda p: abs(p[1] - shape.at(min(max(p[0], 0), 1))[0]))[0]
    if len(tips) < 3:
        return
    count = max(7, min(13, len(tips)))
    picks = [tips[round(i * (len(tips) - 1) / (count - 1))] for i in range(count)]
    for i, (t, z) in enumerate(picks):
        if side:
            foot_t = min(max(front[0], 0.02), 0.995)
            w, hh = K.radii(foot_t)
            root = Vector((LENGTH / 2 - foot_t * LENGTH, side * w * 0.9, front[1] * LENGTH))
        else:
            # rooted ahead of the tip, part-way back along the base, so the streamer trails toward the tail
            foot_t = base_lo + (min(max(t, base_lo), base_hi) - base_lo) * 0.55
            foot_t = min(max(foot_t, 0.02), 0.995)
            mid, h = shape.at(foot_t)
            w, hh = K.radii(foot_t)
            root = Vector((LENGTH / 2 - foot_t * LENGTH, ((i % 3) - 1) * 0.04, mid * LENGTH + (hh if z >= mid else -hh) * 0.8))
        tip = Vector((LENGTH / 2 - t * LENGTH, 0, z * LENGTH))
        flat = Vector((tip.x - root.x, 0, tip.z - root.z))
        length = flat.length * reach
        if length < 0.08:
            continue
        flat.normalize()
        if side:
            direction = Vector((flat.x * math.cos(splay), side * math.sin(splay), flat.z)).normalized()
            out = Vector((0, 0, 1))
        else:
            direction = flat
            out = Vector((0, 1 if i % 2 else -1, 0))
        nxt, prv = picks[min(i + 1, count - 1)], picks[max(i - 1, 0)]
        gap = math.hypot(nxt[0] - prv[0], nxt[1] - prv[1]) * LENGTH / 2
        width = max(0.16, min(0.5, gap * 1.25))
        main, tipc = stripes[(i + shift) % len(stripes)], stripes[(i + shift + 2) % len(stripes)]
        K.strip(bm, col, root, direction, out, length, width, main, curl=0.07, segs=5, bands=[main, main, main, main, tipc])
        # a shorter under-layer, turned a little and set well clear of the first so the two never share a plane
        turn = 0.12 if i % 2 else -0.12
        under = Vector((direction.x * math.cos(turn) - direction.z * math.sin(turn), direction.y, direction.x * math.sin(turn) + direction.z * math.cos(turn)))
        K.strip(bm, col, root - out * 0.09, under, -out, length * 0.55, width * 0.9, tipc, curl=0.16, segs=3)


def ball(parent, name, centre, r, material, squash=(1, 1, 1), tilt=0.0):
    bm_ = bmesh.new()
    bmesh.ops.create_uvsphere(bm_, u_segments=24, v_segments=14, radius=r)
    o = K.new_object(name, bm_, smooth=True)
    o.location, o.scale = centre, squash
    o.rotation_euler = (tilt, 0, 0)
    o.data.materials.append(material)
    o.parent = parent
    return o


def face(body, bm, col, shape, pal, seed, eye, style, big=1.0, red_eyes=False):
    eye_t, eye_z, eye_r = eye
    eye_t = max(eye_t, NOSE * 0.9)
    c, d, side, up = K.frame(eye_t)
    w, h = K.radii(eye_t)
    rel = max(-0.5, min(0.75, (eye_z * LENGTH - c.z) / h))
    phi = math.asin(rel)
    r = max(0.16, min(0.25, eye_r * LENGTH * 2.2))
    r *= {"beady": 0.72, "wide": 1.22}.get(style, 1.0) * big
    white = K.flat_material("EyeWhite", (1, 1, 1), 0.25)
    pupil = K.flat_material("PupilRed" if red_eyes else "Pupil", (0.75, 0.08, 0.12) if red_eyes else (0.03, 0.03, 0.04), 0.15)
    iris = K.flat_material(f"Iris{seed}", pal["teal"] if style != "wide" else pal["gold"], 0.3)
    lid = K.flat_material(f"Lid{seed}{style}", pal["mark"][0], 0.7)
    ring = K.flat_material(f"Ring{seed}", pal["gold"], 0.5)
    for sgn in (-1, 1):
        centre = Vector((c.x, sgn * w * math.cos(phi) * 0.92, c.z + h * math.sin(phi)))
        look = (Vector((0, sgn, 0.2)).normalized() * 0.8 + Vector((0.6, 0, 0))).normalized()
        if style == "beady":
            ball(body, "EyeRing", centre - Vector((0, sgn * r * 0.25, 0)), r * 1.5, ring, squash=(1, 0.5, 1))
        ball(body, "Eye", centre, r, white)
        if style in ("round", "lashes", "wide", "grumpy"):
            ball(body, "Iris", centre + look * r * 0.5, r * 0.66, iris)
        size = {"wide": 0.3, "beady": 0.7, "sleepy": 0.46}.get(style, 0.42)
        ball(body, "Pupil", centre + look * r * (0.66 if style != "beady" else 0.45), r * size, pupil)
        ball(body, "Glint", centre + look * r * 0.98 + Vector((0, 0, r * 0.28)), r * 0.13, K.flat_material("Glint", (1, 1, 1), 0.2, emit=1.0))
        if style in ("round", "lashes"):
            ball(body, "Lid", centre + Vector((-r * 0.14, 0, r * 0.32)), r * 1.04, lid, squash=(1, 1, 0.7))
        elif style == "sleepy":
            ball(body, "Lid", centre + Vector((-r * 0.05, 0, r * 0.1)), r * 1.05, lid, squash=(1, 1, 0.9))
        elif style == "grumpy":
            ball(body, "Lid", centre + Vector((r * 0.05, 0, r * 0.34)), r * 1.06, lid, squash=(1, 1, 0.66), tilt=-sgn * 0.0).rotation_euler = (0, 0.55, 0)
        if style == "lashes":
            for k in range(3):
                a = -0.5 + k * 0.5
                K.strip(bm, col, centre + Vector((0, sgn * r * 0.3, r * 0.8)), Vector((-math.sin(a) * 0.6, sgn * 0.5, math.cos(a))).normalized(), Vector((0, sgn, 0)), r * 1.1, r * 0.3, pal["deep"], curl=0.4, segs=3)
        ball(body, "Cheek", Vector((c.x + r * 0.5, sgn * w * 0.95, c.z - h * 0.4)), r * 0.45, K.flat_material("Cheek", (1.0, 0.5, 0.66), 0.8), squash=(0.9, 0.35, 0.8))
    # a small mouth set into the rounded nose, and for some designs paper whiskers
    nose, _, _, _ = K.frame(0.012)
    ball(body, "Lips", nose, 0.085, K.flat_material("Lips", (1.0, 0.5, 0.66), 0.5), squash=(0.55, 1.0, 0.7))
    ball(body, "Mouth", nose + Vector((0.035, 0, 0)), 0.045, K.flat_material("Pupil", (0.03, 0.03, 0.04), 0.15), squash=(0.5, 1, 0.6))
    if seed % 3 == 0:
        for sgn in (-1, 1):
            K.strip(bm, col, nose + Vector((-0.05, sgn * 0.08, -0.05)), Vector((0.2, sgn * 0.8, -0.5)).normalized(), Vector((0, 0, -1)), 0.6, 0.07, pal["gold"], curl=-0.5, segs=6)


def crest(bm, col, shape, pal, tall=1.0, start=0.1, end=0.34, crown=False):
    n = 9
    for i in range(n):
        t = start + (end - start) * i / (n - 1)
        c, d, side, up = K.frame(t)
        w, h = K.radii(t)
        length = (0.3 + 0.35 * math.sin((i + 1) / (n + 1) * math.pi)) * tall
        colour = pal["gold"] if crown else (pal["mark"][i % 2])
        K.strip(bm, col, c + up * h * 0.9, (up * 0.9 + d * 0.35).normalized(), -d, length, 0.17, colour, curl=0.25, segs=4,
                bands=[pal["gold"], pal["deep"], pal["gold"], pal["body"][0]] if crown else None)


def build(seed, index, origin, variant="common", wild=(), pal_index=None):
    """pal_index picks the palette without changing the face, which `index` also seeds."""
    data = json.loads((DATA / f"fish_{seed}.json").read_text())
    rng = random.Random(seed)
    pal = PALETTES[(index if pal_index is None else pal_index) % len(PALETTES)]
    if variant == "colour":
        pal = PALETTES[(index + 3) % len(PALETTES)]
    elif RARES.get(variant):
        pal = RARES[variant]
    shape = Shape(data)
    install(shape, pal, fat=1.45 if "chubby" in wild else 1.0, fluffy="fluffy" in wild)
    eye = data["eye"] or (0.18, 0.0, 0.03)
    c, d, side, up = K.frame(max(eye[0], NOSE * 0.9))
    w, h = K.radii(max(eye[0], NOSE * 0.9))
    K.EYE_T, K.EYE_PHI = max(eye[0], NOSE * 0.9), math.asin(max(-0.5, min(0.75, (eye[1] * LENGTH - c.z) / h)))
    K.rng = random.Random(seed + 7)
    if variant == "rainbow":
        def rainbow(coat, t, phi, row, k=0):
            got = COLOUR_AT(coat, t, phi, row, k)
            return colorsys.hsv_to_rgb((row / K.ROWS * 1.4) % 1.0, 0.78, 1.0) if got in K.WHITE or got in K.RED else got
        K.colour_at = rainbow
    else:
        K.colour_at = COLOUR_AT
    body = K.build_fish(Markings(rng))
    K.colour_at = COLOUR_AT
    paper = body.data.materials[0]

    bm = bmesh.new()
    col = bm.loops.layers.color.new("Col")
    reach = 1.9 if "long fins" in wild else 1.0
    median = data["fins"]["median"]
    tail = max(median, key=lambda p: sum(q[0] for q in p) / len(p)) if median else None
    for i, poly in enumerate(median):
        if poly is tail and "twin tail" in wild:
            for sgn in (-1, 1):
                streamer_fin(bm, col, shape, poly, pal, side=sgn * 0.6, splay=0.75, reach=reach, shift=i + (0 if sgn < 0 else 3))
        else:
            streamer_fin(bm, col, shape, poly, pal, reach=reach, shift=i)
    for key, splay in (("pectoral", 0.95), ("pelvic", 0.6)):
        poly = data["fins"][key]
        if poly:
            for sgn in (-1, 1):
                streamer_fin(bm, col, shape, poly, pal, side=sgn, splay=splay, reach=reach, shift=2)
    if seed % 2 == 1 or "crown" in wild:
        crest(bm, col, shape, pal, tall=2.4 if "crown" in wild else 1.0, crown="crown" in wild)
    style = EYE_STYLES[(seed * 7 + index) % len(EYE_STYLES)]
    face(body, bm, col, shape, pal, seed, eye, style, big=1.75 if "giant eyes" in wild else 1.0, red_eyes=variant == "albino")
    extras = K.new_object(f"Extras{seed}{variant}", bm)
    extras.data.materials.append(paper)
    extras.parent = body
    body.location = origin
    return data["name"], style


def sheet(scene, out, cells, cols, view=(0, -1, 0), dx=6.0, dz=3.9):
    """cells: (seed, palette index, variant, wild traits). Lays them out in a grid and renders one picture."""
    from bpy_extras.object_utils import world_to_camera_view
    rows = math.ceil(len(cells) / cols)
    placed = []
    for i, (seed, index, variant, wild) in enumerate(cells):
        origin = Vector(((i % cols - (cols - 1) / 2) * dx, 0, -(i // cols) * dz))
        name, style = build(seed, index, origin, variant, wild)
        label = "Wildcard: " + " + ".join(wild) if wild else {"common": f"{name} ({seed})", "colour": "Colour variant"}.get(variant, "Rare: " + variant)
        placed.append((label, origin))
        print("built", seed, variant, wild)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=80)
    back = K.new_object("Backdrop", bm)
    back.rotation_euler = (math.pi / 2, 0, 0)
    back.location = (0, 2.4, 0)
    back.data.materials.append(K.flat_material("Backdrop", (0.80, 0.76, 0.66), 0.95))
    width, height = cols * dx + 0.8, rows * dz + 0.6
    cz = -(rows - 1) * dz / 2 - 0.3
    res = (2600, round(2600 * height / width))
    d = Vector(view).normalized()
    K.shoot(scene, out, tuple(Vector((0, 0, cz)) + d * 60), (0, 0, cz), ortho=width * (1.0 if view == (0, -1, 0) else 1.08), res=res)
    cam = scene.camera
    marks = []
    for label, origin in placed:
        v = world_to_camera_view(scene, cam, origin + Vector((0, -0.6, -1.6)))
        marks.append([label, round(v.x * res[0], 1), round((1 - v.y) * res[1], 1)])
    (DATA / f"{out}.json").write_text(json.dumps({"size": list(res), "cells": marks}, indent=1))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {"--samples": "64", "--out": "sheet", "--mode": "commons", "--cols": "5"}
    for flag in list(opts):
        if flag in argv:
            i = argv.index(flag)
            opts[flag] = argv[i + 1]
            del argv[i:i + 2]
    seeds = [int(a) for a in argv]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = K.scene_setup(int(opts["--samples"]))
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.86, 0.92, 1.0, 1)
    if opts["--mode"] == "commons":
        sheet(scene, opts["--out"], [(seed, i, "common", ()) for i, seed in enumerate(seeds)], int(opts["--cols"]))
    elif opts["--mode"] == "wildcards":          # one design: common, then one odd trait at a time, then two stacked
        seed = seeds[0]
        index = int(seeds[1]) if len(seeds) > 1 else 0
        traits = ["twin tail", "giant eyes", "fluffy", "crown", "long fins", "chubby"]
        cells = [(seed, index, "common", ())] + [(seed, index, "common", (t,)) for t in traits] + [(seed, index, "common", ("crown", "long fins", "giant eyes"))]
        sheet(scene, opts["--out"], cells, 4, view=(0.5, -1, 0.42), dx=6.6, dz=4.6)
    else:                                        # the four-version grid: common, colour variant, rare, wildcard
        cells = []
        for r, seed in enumerate(seeds):
            cells += [(seed, r, "common", ()), (seed, r, "colour", ()), (seed, r, RARE_ORDER[r % 4], ()), (seed, r, "common", WILD_ORDER[r % 4])]
        sheet(scene, opts["--out"], cells, 4)


if __name__ == "__main__":
    main()
