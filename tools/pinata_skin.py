"""Paper skin for a piñata creature, done the way the reference game does it (seen in a real body texture):

  1. big flat colour regions with curved borders, painted in the texture;
  2. a pale line along every border, with a row of short stitch marks beside it;
  3. the whole surface tiled with overlapping paper rectangles, each a slightly different shade and darker
     toward its lower edge, like shingles;
  4. shell texturing on top: copies of the body pushed out along its normals, each showing only the scraps
     tall enough to reach it, brighter the higher they are.

Blender module (uses numpy and bpy only). The mesh needs UVs and a material slot per body part.

    dif, height = bake(obj, region_fn, palette, accent, name)     # paints art/pinata/skins/<name>_dif/_h.png
    skin(obj, dif, height, shells=8, depth=0.12)                  # base material + the shell copies
"""
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SKINS = ROOT / "art" / "pinata" / "skins"


def _shift(a, dx, dy, fill):
    out = np.full_like(a, fill)
    h, w = a.shape[:2]
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    out[yd, xd] = a[ys, xs]
    return out


def _save(name, rgba, colourspace):
    h, w = rgba.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.colorspace_settings.name = colourspace       # before the pixels: changing it afterwards clears them
    img.pixels.foreach_set(np.ascontiguousarray(rgba, np.float32).ravel())
    img.update()
    SKINS.mkdir(parents=True, exist_ok=True)
    img.filepath_raw = str(SKINS / f"{name}.png")
    img.file_format = "PNG"
    img.save()
    return img


def bake(obj, region_fn, palette, accent, name, size=1024, tiles=(26, 34), style="shingles", line=(1.0, 0.98, 0.92), scrap=None, coords=None):
    """region_fn(points (n, 3) in object space, part index) -> palette index per point, or a pair
    (palette index, ink index) where ink is a painted mark laid over the regions (-1 for none).

    style "shingles" tiles the whole surface with overlapping paper rectangles.
    style "dashes" follows the split measured in docs/PINATA_RULES.md: the colour map is flat and painterly,
    and the paper is a separate sparse pattern of short level dashes over about a fifth of the surface. A dash
    lightens the colour where a scrap sits and shades the strip under it, and is also the height map.
    scrap (dashes only) tunes that pattern: dict(on=share of cells with a scrap, width=(least, most) share of
    the cell a scrap spans, top=where in the cell it starts, deep=where its lower edge is, tone=how much lighter
    a scrap is, under=how dark the strip beneath it is). Left out, the pattern is as before."""
    me = obj.data
    me.calc_loop_triangles()
    uv = me.uv_layers.active.data
    # coords names a second UV layer holding the surface's own coordinates (say, distance along the body and height
    # round it). When given, region_fn gets them as a third argument, so paint can be designed on the form itself
    # and wrap right round it, instead of being projected through it from one side.
    own = me.uv_layers[coords].data if coords else None
    rid = np.full((size, size), -1, np.int16)
    ink = np.full((size, size), -1, np.int16)
    for tri in me.loop_triangles:
        p = np.array([me.vertices[v].co[:] for v in tri.vertices])
        t = np.array([uv[l].uv[:] for l in tri.loops]) * size
        x0, x1 = int(max(0, np.floor(t[:, 0].min()))), int(min(size - 1, np.ceil(t[:, 0].max())))
        y0, y1 = int(max(0, np.floor(t[:, 1].min()))), int(min(size - 1, np.ceil(t[:, 1].max())))
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (t[1, 1] - t[2, 1]) * (t[0, 0] - t[2, 0]) + (t[2, 0] - t[1, 0]) * (t[0, 1] - t[2, 1])
        if abs(d) < 1e-9:
            continue
        a = ((t[1, 1] - t[2, 1]) * (gx - t[2, 0]) + (t[2, 0] - t[1, 0]) * (gy - t[2, 1])) / d
        b = ((t[2, 1] - t[0, 1]) * (gx - t[2, 0]) + (t[0, 0] - t[2, 0]) * (gy - t[2, 1])) / d
        c = 1 - a - b
        inside = (a >= -0.02) & (b >= -0.02) & (c >= -0.02)
        if not inside.any():
            continue
        pts = a[inside][:, None] * p[0] + b[inside][:, None] * p[1] + c[inside][:, None] * p[2]
        if own is not None:
            q = np.array([own[l].uv[:] for l in tri.loops])
            got = region_fn(pts, tri.material_index, a[inside][:, None] * q[0] + b[inside][:, None] * q[1] + c[inside][:, None] * q[2])
        else:
            got = region_fn(pts, tri.material_index)
        rid[y0:y1 + 1, x0:x1 + 1][inside] = got[0] if isinstance(got, tuple) else got
        if isinstance(got, tuple):
            ink[y0:y1 + 1, x0:x1 + 1][inside] = got[1]
    for _ in range(6):                                   # bleed past the island edges so seams do not show
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n, ni = _shift(rid, dx, dy, -1), _shift(ink, dx, dy, -1)
            grow = (rid < 0) & (n >= 0)
            rid = np.where(grow, n, rid)
            ink = np.where(grow, ni, ink)
    valid = rid >= 0
    pal = np.array(palette, np.float32)
    rgb = pal[np.clip(rid, 0, len(pal) - 1)]

    # 3. shingles: rows of rectangles, alternate rows offset by half a tile
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float32)
    tw, th = size / tiles[0], size / tiles[1]
    row = np.floor(ys / th)
    xo = xs + (row % 2) * tw / 2
    col = np.floor(xo / tw)
    u, v = (xo / tw) % 1, 1 - (ys / th) % 1               # v runs from a tile's top (0) to its lower edge (1)
    rnd = np.modf(np.sin(col * 127.1 + row * 311.7) * 43758.5453)[0] % 1
    if style == "plain":
        rgb = rgb * (1.0 + ((np.sin(xs * 0.021 + np.sin(ys * 0.017) * 2.1) + np.sin(ys * 0.026)) * 0.02)[..., None])
    elif style == "dashes":
        # painterly ground: broad soft blotches a few percent lighter and darker, as if brushed on
        mottle = (np.sin(xs * 0.021 + np.sin(ys * 0.017) * 2.1) + np.sin(ys * 0.026 + np.sin(xs * 0.013) * 1.7)) * 0.022
        rgb = rgb * (1.0 + mottle[..., None])
        # the paper: one short dash in about three cells out of four
        sc = dict(on=0.78, width=(0.58, 0.58), top=0.24, deep=0.72, tone=0.16, under=0.84, lift=1.04, jitter=0.0)
        sc.update(scrap or {})
        on = rnd < sc["on"]
        tone = np.modf(np.sin(col * 53.7 + row * 91.3) * 9631.7)[0] % 1     # each scrap a little lighter or darker than the next
        wide = sc["width"][0] + (sc["width"][1] - sc["width"][0]) * ((tone * 7.1) % 1)   # and each its own length
        u0 = 0.08 + (0.84 - wide) * ((rnd * 5.3) % 1) * sc["jitter"]        # and, with jitter, sitting anywhere in its cell
        span = on & (u > u0) & (u < u0 + wide)
        dash = span & (v > sc["top"]) & (v < sc["deep"])
        under = span & (v >= sc["deep"]) & (v < min(0.98, sc["deep"] + 0.26))
        rgb = np.where(dash[..., None], rgb * (sc["lift"] + sc["tone"] * tone)[..., None], rgb)
        rgb = np.where(under[..., None], rgb * sc["under"], rgb)
    else:
        shade = (0.88 + 0.20 * rnd) * (1.0 - 0.34 * v ** 2.2)    # baked shading: each scrap darkens toward its lower edge
        shade = np.where(v < 0.12, shade * 0.72, shade)       # the shadow of the tile above
        shade = np.where((u < 0.04) | (u > 0.96), shade * 0.88, shade)
        rgb = rgb * shade[..., None]

    # 2. borders: a pale line, and stitches beside it on the side of the higher-numbered region
    border = np.zeros((size, size), bool)
    hi = np.zeros((size, size), np.int16)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = _shift(rid, dx, dy, -1)
        edge = valid & (n >= 0) & (n != rid)
        border |= edge
        hi = np.where(edge, np.maximum(rid, n), hi)
    dist = np.where(border, 0, 99).astype(np.int16)
    for i in range(1, 15):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nd, nh = _shift(dist, dx, dy, 99), _shift(hi, dx, dy, 0)
            take = (nd == i - 1) & (dist > i)
            dist = np.where(take, i, dist)
            hi = np.where(take, nh, hi)
    k = size / 1024
    edge_line = valid & (dist <= 2 * k)
    rgb = np.where(edge_line[..., None], rgb * 0.25 + np.array(line, np.float32) * 0.75, rgb)
    stitch = valid & (dist >= 7 * k) & (dist <= 13 * k) & (rid == hi) & ((np.floor((xs + 2 * ys) / (11 * k)) % 2) == 0)
    rgb = np.where(stitch[..., None], np.array(accent, np.float32), rgb)
    # painted marks go on last, flat, over everything
    marked = valid & (ink >= 0)
    rgb = np.where(marked[..., None], pal[np.clip(ink, 0, len(pal) - 1)], rgb)

    # 4. the height of each scrap, for the bump and the shells
    tall = np.modf(np.sin(col * 269.5 + row * 183.3) * 24634.6345)[0] % 1
    if style == "plain":
        # no paper: the painted marks and the borders stand a little proud, like a pattern pressed into the skin
        height = np.where(marked | edge_line, 1.0, 0.0).astype(np.float32)
        for _ in range(2):
            height = (height + _shift(height, 1, 0, 0) + _shift(height, -1, 0, 0) + _shift(height, 0, 1, 0) + _shift(height, 0, -1, 0)) / 5
    elif style == "dashes":
        # each scrap rises from its glued top edge to its free lower edge, so every shell up cuts it shorter
        # and it reads as a lifted flap rather than a block (the fade a painted strip tile is given by hand)
        ramp = np.clip((v - sc["top"]) / max(1e-3, sc["deep"] - sc["top"]), 0, 1) ** 0.7
        height = np.where(dash & valid, (0.35 + 0.65 * tall) * (0.25 + 0.75 * ramp), 0.0)
        gap = valid & ~dash & ~under & ~marked            # and the gaps between scraps sit a little in shadow
        rgb = np.where(gap[..., None], rgb * 0.95, rgb)
    else:
        flap = (v > 0.28) & (u > 0.08) & (u < 0.92)        # only the lower flap of a tile lifts, and not every tile
        height = np.where(flap & valid, 0.25 + 0.75 * tall, 0.0) * np.clip((v - 0.28) / 0.3, 0, 1) ** 0.5

    rgba = np.dstack([np.clip(rgb, 0, 1), np.ones((size, size), np.float32)])
    hmap = np.dstack([height, height, height, np.ones((size, size), np.float32)])
    return _save(f"{name}_dif", rgba, "sRGB"), _save(f"{name}_h", hmap, "Non-Color")


def _material(name, dif, height, bright, threshold=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.85
    b.inputs["Sheen Weight"].default_value = 0.3
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image, tex.interpolation = dif, "Linear"      # the colour is smoothed; only the scrap mask stays hard-edged
    mul = nt.nodes.new("ShaderNodeMixRGB")
    mul.blend_type, mul.inputs[0].default_value = "MULTIPLY", 1.0
    mul.inputs[2].default_value = (bright, bright, bright, 1)
    nt.links.new(tex.outputs["Color"], mul.inputs[1])
    nt.links.new(mul.outputs["Color"], b.inputs["Base Color"])
    h = nt.nodes.new("ShaderNodeTexImage")
    h.image, h.interpolation = height, "Closest"
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.7
    bump.inputs["Distance"].default_value = 0.05
    nt.links.new(h.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    if threshold is not None:
        gt = nt.nodes.new("ShaderNodeMath")
        gt.operation = "GREATER_THAN"
        gt.inputs[1].default_value = threshold
        nt.links.new(h.outputs["Color"], gt.inputs[0])
        nt.links.new(gt.outputs["Value"], b.inputs["Alpha"])
    return m


def skin(obj, dif, height, shells=4, depth=0.05, base_bright=0.70):
    """Give obj the painted base and add the shell copies. Returns the shell objects."""
    me = obj.data
    me.materials.clear()
    me.materials.append(_material(obj.name + "_base", dif, height, base_bright))
    for p in me.polygons:
        p.material_index = 0
        p.use_smooth = True
    made = []
    for k in range(1, shells + 1):
        copy = obj.copy()
        copy.data = me.copy()
        copy.name = f"{obj.name}_shell{k}"
        bpy.context.scene.collection.objects.link(copy)
        for vert in copy.data.vertices:
            vert.co = vert.co + vert.normal * (depth * k / shells)
        copy.data.materials.clear()
        copy.data.materials.append(_material(f"{obj.name}_shell{k}", dif, height, 0.76 + 0.34 * k / shells, threshold=(k - 0.5) / shells))
        copy.parent = obj
        copy.location, copy.rotation_euler, copy.scale = (0, 0, 0), (0, 0, 0), (1, 1, 1)
        made.append(copy)
    return made


def _tab_mask():
    """What a row of paper looks like from the side: square tabs of uneven length. u runs along the row."""
    name = "pinata_tabs"
    if name in bpy.data.images:
        return bpy.data.images[name]
    w, h, tabs = 512, 64, 16
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    u, v = xs / w * tabs, ys / (h - 1)
    reach = 0.5 + 0.5 * (np.modf(np.sin(np.floor(u) * 91.7) * 9631.3)[0] % 1)
    a = ((v < reach) & (u % 1 > 0.07) & (u % 1 < 0.93)).astype(np.float32)
    return _save(name, np.dstack([a, a, a, np.ones_like(a)]), "Non-Color")


def fins(obj, dif, height=0.16, droop=0.75, keep=1.0, tab=0.16, level=0.35, where=None):
    """Edge fins: a card standing on each roughly level edge of the body, leaning outward and down, carrying
    the colour of the surface under it and cut into paper tabs. A card only shows where it faces the viewer,
    which is at the creature's outline, so the outline goes ragged while the body stays clean."""
    import bmesh
    from mathutils import Vector
    src = bmesh.new()
    src.from_mesh(obj.data)
    src_uv = src.loops.layers.uv.active
    out = bmesh.new()
    uv, fuv = out.loops.layers.uv.new("UVMap"), out.loops.layers.uv.new("fin")
    down = Vector((0, 0, -1))
    for e in src.edges:
        a, b = e.verts
        d = (b.co - a.co)
        if d.length < 1e-4 or abs(d.normalized().z) > level or not e.link_loops:
            continue
        # where(point) -> (share kept, height factor) thins and shortens the paper locally, for faces and feet
        keep_here, tall = where((a.co + b.co) / 2) if where else (1.0, 1.0)
        if keep * keep_here < 1 and (np.modf(np.sin(e.index * 12.9898) * 43758.5453)[0] % 1) > keep * keep_here:
            continue
        lp = e.link_loops[0]
        uvs = {lp.vert.index: lp[src_uv].uv.copy(), lp.link_loop_next.vert.index: lp.link_loop_next[src_uv].uv.copy()}
        tops = []
        for vert in (a, b):
            lean = (vert.normal * 1.0 + down * droop).normalized()
            tops.append(vert.co + lean * height * tall)
        quad = [out.verts.new(a.co), out.verts.new(b.co), out.verts.new(tops[1]), out.verts.new(tops[0])]
        f = out.faces.new(quad)
        u0 = (np.modf(np.sin(e.index * 78.233) * 1234.5)[0] % 1) * 8
        u1 = u0 + d.length / tab / 16
        for loop, (key, fu, fv) in zip(f.loops, ((a.index, u0, 0), (b.index, u1, 0), (b.index, u1, 1), (a.index, u0, 1))):
            loop[uv].uv = uvs[key]
            loop[fuv].uv = (fu, fv)
    src.free()
    me = bpy.data.meshes.new(obj.name + "_fins")
    out.to_mesh(me)
    out.free()
    o = bpy.data.objects.new(obj.name + "_fins", me)
    bpy.context.scene.collection.objects.link(o)
    o.parent = obj

    m = bpy.data.materials.new(obj.name + "_fins")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.85
    base_uv = nt.nodes.new("ShaderNodeUVMap")
    base_uv.uv_map = "UVMap"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image, tex.interpolation = dif, "Linear"      # the colour is smoothed; only the scrap mask stays hard-edged
    nt.links.new(base_uv.outputs["UV"], tex.inputs["Vector"])
    lift = nt.nodes.new("ShaderNodeMixRGB")
    lift.blend_type, lift.inputs[0].default_value, lift.inputs[2].default_value = "MULTIPLY", 1.0, (1.12, 1.12, 1.12, 1)
    nt.links.new(tex.outputs["Color"], lift.inputs[1])
    nt.links.new(lift.outputs["Color"], bsdf.inputs["Base Color"])
    fin_uv = nt.nodes.new("ShaderNodeUVMap")
    fin_uv.uv_map = "fin"
    tabs = nt.nodes.new("ShaderNodeTexImage")
    tabs.image, tabs.interpolation = _tab_mask(), "Closest"
    nt.links.new(fin_uv.outputs["UV"], tabs.inputs["Vector"])
    facing = nt.nodes.new("ShaderNodeLayerWeight")       # 0 where the card faces the viewer, 1 where it is edge-on
    facing.inputs["Blend"].default_value = 0.35
    show = nt.nodes.new("ShaderNodeMath")
    show.operation = "LESS_THAN"
    show.inputs[1].default_value = 0.55
    nt.links.new(facing.outputs["Facing"], show.inputs[0])
    alpha = nt.nodes.new("ShaderNodeMath")
    alpha.operation = "MULTIPLY"
    nt.links.new(tabs.outputs["Color"], alpha.inputs[0])
    nt.links.new(show.outputs["Value"], alpha.inputs[1])
    nt.links.new(alpha.outputs["Value"], bsdf.inputs["Alpha"])
    me.materials.append(m)
    return o
