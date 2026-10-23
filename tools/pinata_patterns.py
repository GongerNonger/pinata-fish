"""Paper piñata coat patterns: a small folk-art vocabulary, combined per fish into a recipe.

Every scrap of fringe (and every face of the smooth head) asks for its colour by where it sits on the body. This
module answers with a *role* (body, mark, gold, teal, deep, belly), and the fish's palette turns the role into
a colour, so one recipe works in every colourway, rare and wildcard.

The rules from docs/HOW_THE_PAPER_WORKS.md that shape it:
- one bold base layout per fish, and at most two accents over it, never an all-over busy print;
- every mark is several scraps wide (a scrap is about 0.11 x 0.14 body units), or it disappears;
- regions meet along curved borders, often with a row of stitches beside them.

Positions are "painter's coordinates": the fish seen from the side, with the flank unrolled. x runs along the
body from the nose (body units), y runs up the flank from the lateral line (body units), and `up` is the same
height as a fraction: 0 on the lateral line, 1 on the ridge of the back, -1 under the belly. Both flanks get
the same picture.

    recipe = Recipe.from_seed(404)                 # or Recipe("saddles", [("sun", {})], face="mask")
    role = recipe.role(t, phi, row, k)             # for a fringe scrap
    role = recipe.face_role(t, phi)                # for the smooth head
"""
import math
import random

import build_pinata_koi as K

ROLES = ("body", "body2", "mark", "mark2", "gold", "teal", "deep", "belly", "pink", "white")


def colour(pal, role, row=0):
    """A role in a palette (build_pinata_fish.PALETTES), as an sRGB tuple. Body and mark alternate their two
    shades by row, which is what gives the fringe its staggered, many-scrap look."""
    if role == "body":
        return pal["body"][row % 2]
    if role == "body2":
        return pal["body"][(row + 1) % 2]
    if role == "mark":
        return pal["mark"][row % 2]
    if role == "mark2":
        return pal["mark"][(row + 1) % 2]
    if role == "belly":
        return tuple(min(1.0, c * 0.6 + 0.42) for c in pal["body"][0])
    if role == "pink":
        return (1.0, 0.5, 0.66)
    if role == "white":
        return (1.0, 0.98, 0.94)
    return pal[role]


def tri(u):
    """A triangle wave, 0..1..0 over each unit."""
    u = u % 1.0
    return 1 - abs(2 * u - 1)


def painter(t, phi):
    """x along the body, y up the flank and `up` (-1..1) for a point on the body at t, angle phi."""
    tc = min(max(t, 0.0), 1.0)
    w, h = K.radii(tc)
    a = math.atan2(math.sin(phi), abs(math.cos(phi)))       # 0 on the lateral line, +pi/2 ridge, -pi/2 belly
    return t * K.L, a * (w + h) / 2, a / (math.pi / 2)


# ---- base layouts: each covers the whole body in body and mark ----

def base_plain(p, x, y, up, t, row, k):
    return "body"


def base_saddles(p, x, y, up, t, row, k):
    """Big patches thrown over the back like saddle cloths, each reaching part-way down the flanks."""
    for t0, half, depth in p["saddles"]:
        dx = (t - t0) * K.L / half
        edge = depth + 0.08 * math.sin(x * 4.0 + t0 * 9)
        if dx * dx + ((1 - up) / (1 - edge)) ** 2 < 1:
            return "mark"
    return "body"


def base_cape(p, x, y, up, t, row, k):
    """Countershading: the back in the mark colour down to a wavy line along the flank, stitched along it."""
    line = p["level"] + 0.16 * math.sin(x * p["waves"] + p["phase"])
    if p.get("stitch") and abs(up - line) < 0.08 and k % 2 == 0:
        return "deep"
    return "mark" if up > line else "body"


def base_bands(p, x, y, up, t, row, k):
    """Upright bands round the body, leaning a little and bowed, like wide crepe ribbons wrapped on."""
    u = (x - p["start"] + 0.12 * math.sin(up * 2.4) + p["lean"] * up) / p["period"]
    if t < p["from"] or t > 0.93:
        return "body"
    f = u % 1.0
    if p.get("stitch") and abs(f - p["duty"]) < 0.06 and row % 2 == 0:
        return "deep"
    return "mark" if f < p["duty"] else "body"


def base_harlequin(p, x, y, up, t, row, k):
    """Diamonds, in two colours with every third one gold. Big enough that each holds a dozen scraps."""
    s = p["size"]
    u, v = (x + y) / s, (x - y) / s
    a, b = math.floor(u), math.floor(v)
    if (a + b) % 2:
        return "body"
    return "gold" if (a - b) % 6 == 0 else "mark"


def base_split(p, x, y, up, t, row, k):
    """Front half one colour, back half the other, meeting along a zigzag."""
    edge = p["at"] * K.L + 0.22 * (tri(y / 0.5) - 0.5)
    if p.get("stitch") and abs(x - edge) < 0.09 and row % 2 == 0:
        return "gold"
    return ("mark" if x < edge else "body") if p["front"] == "mark" else ("body" if x < edge else "mark")


def base_spots(p, x, y, up, t, row, k):
    """A few big round spots, each outlined in the deep colour."""
    for sx, sy, r in p["spots"]:
        d = math.hypot(x - sx, y - sy)
        if d < r:
            return "mark"
        if d < r + 0.1 and p.get("outline"):
            return "deep"
    return "body"


def base_stripes(p, x, y, up, t, row, k):
    """Long stripes running nose to tail, gently waved."""
    u = (up + 1) / 2 * p["count"] + 0.12 * math.sin(x * 2.2)
    return "mark" if u % 1.0 < 0.5 else "body"


BASES = {
    "plain": base_plain, "saddles": base_saddles, "cape": base_cape, "bands": base_bands,
    "harlequin": base_harlequin, "split": base_split, "spots": base_spots, "stripes": base_stripes,
}


def base_params(name, rng):
    if name == "saddles":
        n = rng.randint(2, 3)
        return {"saddles": [(0.3 + i * (0.5 / n) + rng.uniform(-0.03, 0.03), rng.uniform(0.32, 0.45), rng.uniform(-0.45, 0.1)) for i in range(n)]}
    if name == "cape":
        return {"level": rng.uniform(-0.15, 0.2), "waves": rng.uniform(2.2, 3.4), "phase": rng.uniform(0, 6), "stitch": rng.random() < 0.6}
    if name == "bands":
        return {"start": rng.uniform(0.6, 0.9), "period": rng.uniform(0.6, 0.85), "duty": rng.uniform(0.35, 0.5), "lean": rng.uniform(-0.25, 0.25),
                "from": 0.2, "stitch": rng.random() < 0.5}
    if name == "harlequin":
        return {"size": rng.uniform(0.8, 0.95)}
    if name == "split":
        return {"at": rng.uniform(0.42, 0.55), "front": rng.choice(["mark", "body"]), "stitch": rng.random() < 0.6}
    if name == "spots":
        spots = []
        for _ in range(rng.randint(3, 5)):
            spots.append((rng.uniform(0.25, 0.8) * K.L, rng.uniform(-0.25, 0.45), rng.uniform(0.2, 0.34)))
        return {"spots": spots, "outline": rng.random() < 0.6}
    if name == "stripes":
        return {"count": rng.choice([2, 3])}
    return {}


# ---- accents: one motif, painted over the base where it says so, None elsewhere ----

def acc_sun(p, x, y, up, t, row, k):
    """A ring with short rays on each flank: gold disc, deep ring, gold rays."""
    dx, dy = x - p["at"] * K.L, y - p.get("y", 0.0)
    d = math.hypot(dx, dy)
    R = p.get("r", 0.6)
    if d < R * 0.42:
        return "gold"
    if d < R * 0.62:
        return "deep"
    if d < R and math.cos(math.atan2(dy, dx) * p.get("rays", 8)) > 0.25:
        return "gold"
    return None


def acc_target(p, x, y, up, t, row, k):
    """Concentric rings on each flank."""
    d = math.hypot(x - p["at"] * K.L, y - p.get("y", 0.0))
    R = p.get("r", 0.6)
    if d < R:
        return ("gold", "teal", "deep", "white")[int(d / R * 4)]
    return None


def acc_dots(p, x, y, up, t, row, k):
    """A row of dots along the flank."""
    if t < 0.5 or t > 0.86:                             # the front of the flank is under the pectoral fan
        return None
    sp = p.get("spacing", 0.46)
    cx = round(x / sp) * sp
    if math.hypot(x - cx, y - p.get("y", 0.0)) < p.get("r", 0.15):
        return p.get("role", "gold")
    return None


def acc_zigzag(p, x, y, up, t, row, k):
    """A zigzag band round the body: teal with gold edges."""
    xc = p["at"] * K.L + 0.22 * (tri(y / 0.45) - 0.5)
    d = abs(x - xc)
    if d < 0.1:
        return "teal"
    if d < 0.19:
        return "gold"
    return None


def acc_teeth(p, x, y, up, t, row, k):
    """A row of triangles standing along the back, alternating gold and deep."""
    if t < 0.22 or t > 0.86:
        return None
    u = x / 0.5
    if up > 1 - 0.85 * tri(u):
        return "gold" if math.floor(u) % 2 else "deep"
    return None


def acc_chevrons(p, x, y, up, t, row, k):
    """Arrowheads pointing to the nose, down the tail half."""
    if t < 0.42 or t > 0.92:
        return None
    v = (x - abs(y) * 0.9) / 0.5
    return "gold" if v % 1.0 < 0.42 else None


def acc_beads(p, x, y, up, t, row, k):
    """Beads down the ridge of the back."""
    if up > 0.74 and t > K.FRINGE0:
        return "gold" if row % 2 else "deep"
    return None


def acc_seam(p, x, y, up, t, row, k):
    """A stitched seam along the lateral line."""
    if abs(y) < 0.13 and 0.22 < t < 0.9:
        return "gold" if row % 2 else "deep"
    return None


def acc_candy(p, x, y, up, t, row, k):
    """Candy rings round the root of the tail."""
    if t > 0.86:
        return ("mark", "white", "gold")[row % 3]
    return None


def acc_collar(p, x, y, up, t, row, k):
    """Alternating blocks at the collar, where the fringe starts behind the head."""
    if row == 0:
        return "gold" if k % 2 == 0 else "deep"
    return None


ACCENTS = {
    "sun": acc_sun, "target": acc_target, "dots": acc_dots, "zigzag": acc_zigzag, "teeth": acc_teeth,
    "chevrons": acc_chevrons, "beads": acc_beads, "seam": acc_seam, "candy": acc_candy, "collar": acc_collar,
}
# accents that need open flank to read on: they go with bases that leave the flank calm
FLANK = {"sun", "target", "dots"}
CALM = {"plain", "cape", "saddles", "split"}


def accent_params(name, rng):
    if name in ("sun", "target"):                       # behind the pectoral fan, which covers the front flank
        return {"at": rng.uniform(0.6, 0.66), "y": rng.uniform(0.0, 0.12), "r": rng.uniform(0.48, 0.58)}
    if name == "dots":
        return {"y": rng.uniform(-0.12, 0.05), "role": rng.choice(["gold", "teal", "white"])}
    if name == "zigzag":
        return {"at": rng.uniform(0.58, 0.72)}
    return {}


# ---- faces: the smooth head is painted, so it takes finer work than the fringe ----

FACES = ("plain", "mask", "blaze", "bonnet", "freckles", "diamond")


def face_role(rec, t, phi):
    x, y, up = painter(t, phi)
    if math.sin(phi) < -0.55 and rec.belly:
        return "belly"
    if t < 0.022:
        return "pink"                                       # lips
    if t < 0.036 and rec.lipstick:
        return "deep"
    w = max(0.03, K.radii(K.EYE_T)[0])
    for phi0 in (K.EYE_PHI, math.pi - K.EYE_PHI):            # rings round the eyes
        dphi = (phi - phi0 + math.pi) % math.tau - math.pi
        d = math.hypot((t - K.EYE_T) * K.L, dphi * w)
        if d < 0.27:
            return "white"
        if d < 0.31 and rec.eye_rings:
            return "teal"
        if d < 0.35 and rec.eye_rings:
            return "gold"
    f = rec.face
    across = abs(((phi - math.pi / 2 + math.pi) % math.tau - math.pi) / math.pi)
    if f == "mask" and abs(t - K.EYE_T) * K.L < 0.3 and up > -0.45:
        return "deep"
    if f == "blaze" and across < 0.1 and 0.03 < t < 0.24:
        return "gold"
    if f == "bonnet" and up > 0.15 + 0.1 * math.sin(t * 40):
        return "mark"
    if f == "freckles" and -0.5 < up < 0.05 and t < 0.2:
        sp = 0.16
        if math.hypot(x - round(x / sp) * sp, y - (-0.25 if (round(x / sp) % 2) else -0.12)) < 0.045:
            return "gold"
    if f == "diamond":
        dia = across / 0.075 + abs(t - 0.07) / 0.04
        if dia < 0.45:
            return "deep"
        if dia < 1:
            return "gold"
    return None


# ---- a recipe: one base, up to two accents, a face ----

class Recipe:
    def __init__(self, base="plain", accents=(), face="plain", belly=True, eye_rings=True, lipstick=True, seed=0, base_p=None):
        rng = random.Random(seed)
        self.base = base
        self.base_p = base_p if base_p is not None else base_params(base, rng)
        self.accents = [(a, p if p else accent_params(a, rng)) for a, p in ((a if isinstance(a, tuple) else (a, None)) for a in accents)]
        self.face, self.belly, self.eye_rings, self.lipstick = face, belly, eye_rings, lipstick

    @classmethod
    def from_seed(cls, seed):
        rng = random.Random(seed * 7919 + 13)
        base = rng.choice(["saddles", "cape", "bands", "harlequin", "split", "spots", "stripes", "saddles", "cape", "plain"])
        pool = ["sun", "target", "dots", "zigzag", "teeth", "chevrons", "beads", "seam", "candy", "collar"]
        if base not in CALM:
            pool = [a for a in pool if a not in FLANK]
        if base in ("bands", "harlequin"):
            pool = [a for a in pool if a not in ("zigzag", "chevrons")]
        accents = rng.sample(pool, rng.choice([1, 2, 2]))
        if base == "plain" and not FLANK & set(accents):
            accents[0] = rng.choice(sorted(FLANK))
        return cls(base, accents, face=rng.choice(FACES), belly=rng.random() < 0.8, eye_rings=rng.random() < 0.7,
                   lipstick=rng.random() < 0.6, seed=seed)

    def describe(self):
        return " + ".join([self.base] + [a for a, _ in self.accents]) + f" / {self.face} face"

    def role(self, t, phi, row, k=0):
        x, y, up = painter(t, phi)
        for name, p in self.accents:
            got = ACCENTS[name](p, x, y, up, t, row, k)
            if got:
                return got
        if self.belly and math.sin(phi) < -0.55:
            return "belly"
        return BASES[self.base](self.base_p, x, y, up, t, row, k)

    def face_role(self, t, phi):
        got = face_role(self, t, phi)
        if got:
            return got
        if t >= K.FRINGE0:                                  # under the fringe: follow the body
            return self.role(t, phi, 1)
        return "mark" if self.base == "cape" and painter(t, phi)[2] > self.base_p["level"] else "body"
