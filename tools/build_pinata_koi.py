"""A look test: one koi rebuilt as a paper pinata creature, rendered beside the current kit koi.

    blender --background --python tools/build_pinata_koi.py -- [--samples 128] [--coat kohaku]

The body is rows of crepe-paper fringe laid like shingles from tail to head, coloured from the same coat strip
the game uses (art/fish/coats/<id>.png), with a smooth paper head, big painted eyes, lips, ribbon barbels,
and fins and tail made of paper streamers. Writes art/pinata/<view>.png. Nothing is exported or uploaded.
"""
import math
import os
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "art" / "pinata" / os.environ.get("PIN_OUT", "")
OUT.mkdir(parents=True, exist_ok=True)
rng = random.Random(4)

import os
STAGE = int(os.environ.get("PIN_STAGE", "4"))
L = 3.4                      # nose to tail root, studs
HALF = L * 0.175             # half-width at the widest point
ROWS = 22
STRIP_W = 0.105
STRIP_LEN = 0.38

WHITE = [(1.0, 0.965, 0.90), (1.0, 0.91, 0.80)]          # alternate rows: warm white, cream
RED = [(1.0, 0.27, 0.10), (1.0, 0.46, 0.08)]             # alternate rows: vermilion, orange
BELLY = (1.0, 0.86, 0.62)
PINK = (1.0, 0.50, 0.66)
GOLD = (1.0, 0.76, 0.16)


def lin(c):
    return tuple(x ** 2.2 for x in c)


def profile(t):
    return 0.62 + 0.38 * math.sin((t / 0.3) * math.pi / 2) if t < 0.3 else 1 - ((t - 0.3) / 0.7) ** 1.9 * 0.8


def frame(t):
    """Centre, tangent toward the tail, sideways and up at t along the body. The nose is at +X."""
    off = lambda u: 0.07 * L * math.sin(u * math.pi * 1.6 - 0.5) * u
    c = Vector((L / 2 - t * L, off(t), 0))
    d = (Vector((L / 2 - (t + 0.01) * L, off(t + 0.01), 0)) - c).normalized()
    side = Vector((-d.y, d.x, 0))
    return c, d, side, Vector((0, 0, 1))


def radii(t):
    w = max(0.03, HALF * profile(t)) * (0.5 if t < 0.02 else 1)
    return w, w * 0.95


class Coat:
    def __init__(self, path):
        img = bpy.data.images.load(str(path))
        self.w, self.h = img.size
        self.px = list(img.pixels)

    def is_marked(self, t, v):
        x = min(self.w - 1, max(0, int(t * self.w)))
        y = min(self.h - 1, max(0, int(v * self.h)))
        i = (y * self.w + x) * 4
        r, g, b = self.px[i:i + 3]
        return r - (g + b) / 2 > 0.18          # a red or orange patch, as opposed to white, black or grey


TEAL = (0.08, 0.70, 0.68)
CRIMSON = (0.70, 0.07, 0.12)
EYE_T, EYE_PHI = 0.13, 0.46      # where the eyes sit: along the body, and up from the side


def across(phi):
    """-1..1 across the back: 0 on the ridge, +-1 at the belly line."""
    d = (phi - math.pi / 2 + math.pi) % math.tau - math.pi
    return d / math.pi


def colour_at(coat, t, phi, row, k=0):
    """The colour of one paper scrap. The koi's own markings (from its coat strip) are the ground; over them go
    the piñata motifs: flat blocks, bands of zigzag, rows of dots, a beaded line down the back, candy rings."""
    if math.sin(phi) < -0.55:
        return BELLY
    s_ = across(phi)
    marked = coat.is_marked(min(t, 0.99), 0.5 + 0.5 * math.cos(phi))
    if STAGE < 3:
        return (RED if marked else WHITE)[row % 2]
    if row == 0:                                     # collar: alternating blocks
        return GOLD if k % 2 == 0 else CRIMSON
    if t > 0.86:                                     # candy rings round the tail root
        return (RED[0], WHITE[0], GOLD)[row % 3]
    if abs(s_) < 0.05:                               # beads down the back
        return GOLD if row % 2 else CRIMSON
    if 6 <= row <= 8:                                # a zigzag band
        zz = (k + abs((row - 6) - 1)) % 4
        if zz == 0:
            return TEAL
        if zz == 1:
            return GOLD if marked else CRIMSON
    if row % 5 == 3 and k % 4 == 0:                  # rows of dots, in the opposite colour
        return GOLD if marked else RED[0]
    return (RED if marked else WHITE)[row % 2]


def head_colour(coat, t, phi):
    """The smooth paper head is painted, not fringed: rings round the eyes, a diamond on the brow, a ringed
    snout and a dotted jaw line, over the koi's own head marking."""
    if math.sin(phi) < -0.55:
        return BELLY
    s_ = across(phi)
    if t < 0.2 and STAGE >= 3:
        w = max(0.03, HALF * profile(EYE_T))
        for phi0 in (EYE_PHI, math.pi - EYE_PHI):
            dphi = (phi - phi0 + math.pi) % math.tau - math.pi
            d = math.hypot((t - EYE_T) * L, dphi * w)
            if d < 0.27:
                return WHITE[0]
            if d < 0.31:
                return TEAL
            if d < 0.35:
                return GOLD
        dia = abs(s_) / 0.075 + abs(t - 0.07) / 0.04
        if dia < 0.45:
            return CRIMSON
        if dia < 1:
            return GOLD
        if t < 0.022:
            return PINK
        if t < 0.036:
            return CRIMSON
        if abs(abs(s_) - 0.6) < 0.04 and t > 0.055 and int(t / 0.02) % 2 == 0:
            return TEAL
    return (RED if coat.is_marked(min(t, 0.99), 0.5 + 0.5 * math.cos(phi)) else WHITE)[0]


def new_object(name, bm, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def paper_material():
    m = bpy.data.materials.new("Paper")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    a = m.node_tree.nodes.new("ShaderNodeVertexColor")
    a.layer_name = "Col"
    m.node_tree.links.new(a.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.78
    b.inputs["Sheen Weight"].default_value = 0.35
    m.use_backface_culling = False
    return m


def flat_material(name, colour, rough=0.4, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = lin(colour) + (1,)
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = lin(colour) + (1,)
        b.inputs["Emission Strength"].default_value = emit
    return m


_SCRAP = 0


def strip(bm, col, base, back, out, length, width, colour, curl=0.16, segs=4, bands=None):
    """One paper strip: rooted at `base`, lying back along the body and curling away from it at the tip."""
    # No two scraps may lie in the same plane, or they flicker where they overlap: each one sits a little
    # higher than the last, cycling through seven heights.
    global _SCRAP
    _SCRAP += 1
    lift = 0.012 + (_SCRAP % 7) * 0.009
    side = back.cross(out).normalized()
    prev = None
    for k in range(segs + 1):
        u = k / segs
        p = base + back * (length * u) + out * (lift + curl * length * u * u)
        w = width / 2 * (1.0 if u < 0.7 else 1.0 - (u - 0.7) * 1.4)
        a, b = bm.verts.new(p - side * w), bm.verts.new(p + side * w)
        if prev:
            f = bm.faces.new((prev[0], prev[1], b, a))
            for lp, uu in zip(f.loops, (prev[2], prev[2], u, u)):
                shade = 0.55 + 0.6 * uu           # dark at the root where the row above shades it, bright at the tip
                lp[col] = tuple(min(1.0, c * shade) for c in lin(bands[(k - 1) % len(bands)] if bands else colour)) + (1,)
        prev = (a, b, u)


def build_fish(coat, origin=Vector((0, 0, 0))):
    paper = paper_material()
    # the smooth core: all of it is covered by fringe except the head
    bm = bmesh.new()
    col = bm.loops.layers.color.new("Col")
    rings, seg = 80, 48
    grid = []
    for i in range(rings + 1):
        t = i / rings
        c, d, side, up = frame(t)
        w, h = radii(t)
        grid.append([(bm.verts.new(c + side * (w * 0.96 * math.cos(k / seg * math.tau)) + up * (h * 0.96 * math.sin(k / seg * math.tau))), t, k / seg * math.tau) for k in range(seg)])
    for i in range(rings):
        for k in range(seg):
            q = [grid[i][k], grid[i][(k + 1) % seg], grid[i + 1][(k + 1) % seg], grid[i + 1][k]]
            f = bm.faces.new([x[0] for x in q])
            flat = lin(head_colour(coat, (q[0][1] + q[2][1]) / 2, q[0][2] + math.pi / seg)) + (1,)
            for lp in f.loops:
                lp[col] = flat
    bm.faces.new([x[0] for x in grid[0]][::-1])
    body = new_object("PinataKoi", bm, smooth=True)
    body.data.materials.append(paper)

    if STAGE < 2:
        body.location = origin
        return body
    # rows of fringe
    bm = bmesh.new()
    col = bm.loops.layers.color.new("Col")
    for row in range(ROWS):
        t = 0.17 + row / (ROWS - 1) * 0.8
        c, d, side, up = frame(t)
        w, h = radii(t)
        n = max(9, int(math.tau * (w + h) / 2 / STRIP_W * 1.5))
        for k in range(n):
            phi = (k + (0.5 if row % 2 else 0)) / n * math.tau + rng.uniform(-0.06, 0.06)
            out = (side * (math.cos(phi) * h) + up * (math.sin(phi) * w)).normalized()
            base = c + side * (w * math.cos(phi)) + up * (h * math.sin(phi))
            strip(bm, col, base, d, out, STRIP_LEN * rng.uniform(0.8, 1.2) * (0.7 + 0.3 * profile(t)) * (0.6 if row == 0 else 1), STRIP_W * 1.3, colour_at(coat, t, phi, row, k))
    # a crest of upright strips along the back
    for i in range(14 if STAGE >= 4 else 0):
        t = 0.3 + i / 13 * 0.4
        c, d, side, up = frame(t)
        w, h = radii(t)
        strip(bm, col, c + up * h * 0.95, (up * 0.8 + d * 0.6).normalized(), -d, 0.26 * math.sin((i + 1) / 15 * math.pi) + 0.1, 0.12, RED[i % 2], curl=0.5, segs=4)
    # pectoral fins: fans of streamers
    for sgn in ((-1, 1) if STAGE >= 4 else ()):
        c, d, side, up = frame(0.3)
        w, h = radii(0.3)
        root = c + side * sgn * w * 0.9 - up * h * 0.35
        for k in range(7):
            a = -0.5 + k / 6 * 1.5
            direction = (side * sgn * math.cos(a) + d * math.sin(a) - up * 0.25).normalized()
            strip(bm, col, root, direction, up, 0.85 * (1 - abs(k - 3) * 0.07), 0.2, WHITE[0], curl=0.12, bands=(RED[0], WHITE[0], GOLD, RED[0]))
    # pelvic fins, smaller
    for sgn in ((-1, 1) if STAGE >= 4 else ()):
        c, d, side, up = frame(0.6)
        w, h = radii(0.6)
        root = c + side * sgn * w * 0.8 - up * h * 0.5
        for k in range(4):
            a = 0.1 + k / 3 * 1.0
            direction = (side * sgn * math.cos(a) + d * math.sin(a) - up * 0.3).normalized()
            strip(bm, col, root, direction, up, 0.5, 0.16, WHITE[k % 2], curl=0.12)
    # the tail: two lobes of long crepe streamers
    c, d, side, up = frame(1.0)
    for lobe in ((-1, 1) if STAGE >= 4 else ()):
        for k in range(8):
            a = lobe * (0.12 + k / 7 * 0.72)
            direction = (d * math.cos(a) + side * math.sin(a)).normalized()
            length = 1.35 * (0.72 + 0.28 * math.sin((k + 1) / 9 * math.pi))
            strip(bm, col, c + up * rng.uniform(-0.03, 0.03), direction, up * (1 if k % 2 else -1), length, 0.26, WHITE[0], curl=0.1, segs=6, bands=(RED[0], WHITE[0], RED[1], WHITE[0], GOLD, CRIMSON) if k % 2 else (WHITE[0], RED[0], WHITE[0], GOLD, RED[0], CRIMSON))
    fringe = new_object("PinataKoi_Fringe", bm)
    fringe.data.materials.append(paper)
    fringe.parent = body
    print("triangles:", (len(body.data.polygons) + len(fringe.data.polygons)) * 2)
    if STAGE < 4:
        body.location = origin
        return body

    # the face: eyes, lids, lips, barbels
    def ball(name, centre, r, material, squash=(1, 1, 1)):
        bm_ = bmesh.new()
        bmesh.ops.create_uvsphere(bm_, u_segments=24, v_segments=14, radius=r)
        o = new_object(name, bm_, smooth=True)
        o.location, o.scale = centre, squash
        o.data.materials.append(material)
        o.parent = body
        return o
    white = flat_material("EyeWhite", (1, 1, 1), 0.25)
    black = flat_material("Pupil", (0.03, 0.03, 0.04), 0.15)
    lid = flat_material("Lid", RED[0], 0.7)
    for sgn in (-1, 1):
        c, d, side, up = frame(0.13)
        w, h = radii(0.13)
        out = (side * sgn * 0.82 + up * 0.57).normalized()
        centre = c + side * sgn * w * 0.86 + up * h * 0.5
        r = 0.21
        ball(f"Eye{sgn}", centre, r, white)
        look = (out * 0.75 - d * 0.66).normalized()
        ball(f"Pupil{sgn}", centre + look * r * 0.62, r * 0.52, black)
        ball(f"Glint{sgn}", centre + look * r * 0.95 + up * r * 0.25, r * 0.14, flat_material("Glint", (1, 1, 1), 0.2, emit=1.0))
        ball(f"Lid{sgn}", centre + up * r * 0.3 + d * r * 0.16, r * 1.04, lid, squash=(1, 1, 0.72))
        ball(f"Cheek{sgn}", c + side * sgn * w * 0.93 - up * h * 0.12 - d * 0.02, 0.13, flat_material("Cheek", PINK, 0.8), squash=(0.9, 0.35, 0.8))
    # lips: a paper ring at the nose
    bm_ = bmesh.new()
    c, d, side, up = frame(0.0)
    mat_rot = Vector((1, 0, 0)).rotation_difference(-d).to_matrix().to_4x4()
    for i in range(20):
        a0 = i / 20 * math.tau
        for j in range(8):
            b0 = j / 8 * math.tau
            pass
    bmesh.ops.create_uvsphere(bm_, u_segments=16, v_segments=10, radius=0.13)
    lips = new_object("Lips", bm_, smooth=True)
    lips.location, lips.scale = c - d * 0.02, (0.6, 1.0, 0.8)
    lips.data.materials.append(flat_material("Lips", PINK, 0.5))
    lips.parent = body
    ball("Mouth", c - d * 0.085, 0.06, black, squash=(0.6, 1, 0.8))
    # barbels: curled gold ribbons
    bm = bmesh.new()
    col = bm.loops.layers.color.new("Col")
    for sgn in (-1, 1):
        strip(bm, col, c + side * sgn * 0.1 - up * 0.06, (side * sgn * 0.8 - up * 0.45 + d * 0.3).normalized(), -up, 0.6, 0.07, GOLD, curl=-0.5, segs=6)
    barbels = new_object("Barbels", bm)
    barbels.data.materials.append(paper)
    barbels.parent = body
    body.location = origin
    return body


def scene_setup(samples):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for dv in prefs.devices:
            dv.use = dv.type == "OPTIX"
        scene.cycles.device = "GPU"
    except Exception as e:
        print("GPU not used:", e)
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "Standard"
    scene.render.image_settings.file_format = "PNG"
    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.78, 1.0, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy, sun.data.angle = 3.2, 0.12
    sun.rotation_euler = (math.radians(48), 0, math.radians(35))
    scene.collection.objects.link(sun)
    return scene


def shoot(scene, name, eye, target, lens=None, ortho=None, res=(1600, 1000)):
    cd = bpy.data.cameras.new(name)
    co = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(co)
    co.location = eye
    co.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cd.type, cd.ortho_scale = "ORTHO", ortho
    else:
        cd.lens = lens
    scene.camera = co
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = str(OUT / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 128
    coat_id = argv[argv.index("--coat") + 1] if "--coat" in argv else "kohaku"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = scene_setup(samples)
    coat = Coat(ROOT / "art" / "fish" / "coats" / f"{coat_id}.png")

    # stage 1: the creature on grass, as a character
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=40)
    grass = new_object("Grass", bm)
    grass.location = (0, 0, -0.62)
    grass.data.materials.append(flat_material("Grass", (0.52, 0.80, 0.30), 0.9))
    fish = build_fish(coat)
    if STAGE < 4:
        shoot(scene, f"stage{STAGE}", (4.6, -4.4, 2.5), (0.2, 0, 0.05), lens=58, res=(1200, 750))
        return
    shoot(scene, "hero", (4.6, -4.4, 2.5), (0.2, 0, 0.05), lens=58)
    shoot(scene, "closeup", (4.4, -1.5, 0.95), (1.2, 0, 0.12), lens=70, res=(1200, 1000))
    shoot(scene, "profile", (0, -8, 0.6), (0, 0, 0.05), lens=75, res=(1600, 700))

    # stage 2: in the pond from above, beside the koi the game has now
    grass.location = (0, 0, -2.2)
    grass.data.materials[0] = flat_material("PondBed", (0.72, 0.80, 0.72), 0.9)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=40)
    water = new_object("Water", bm)
    water.location = (0, 0, 0.45)
    wm = flat_material("Water", (0.25, 0.70, 0.62), 0.05)
    wm.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.28
    water.data.materials.append(wm)
    fish.location = (0, 1.5, 0)
    kit = ROOT / "art" / "kit" / "export" / "Koi.glb"
    if kit.exists():
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(kit))
        added = [o for o in bpy.data.objects if o not in before]
        roots = [o for o in added if o.parent is None]
        for o in roots:
            o.scale = (L / 1.0,) * 3
            o.location = (0.3, -1.7, 0)
            o.rotation_euler = (o.rotation_euler[0], o.rotation_euler[1], math.radians(-90))
    shoot(scene, "frompond", (0.4, 0, 30), (0.4, 0.001, 0), ortho=9.5, res=(1600, 1150))
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "pinata_koi.blend"))


if __name__ == "__main__":
    main()
