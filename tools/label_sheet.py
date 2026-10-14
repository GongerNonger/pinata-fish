"""Label a sheet from tools/build_pinata_fish.py:  python tools/label_sheet.py <name>  ->  art/pinata/fishdraw/<name>_named.jpg"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

d = Path(__file__).resolve().parent.parent / "art" / "pinata" / "fishdraw"
for n in sys.argv[1:]:
    m = json.loads((d / f"{n}.json").read_text())
    im = Image.open(d / f"{n}.png").convert("RGB")
    dr = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype("georgiab.ttf", 28)
    except OSError:
        f = ImageFont.load_default()
    for label, x, y in m["cells"]:
        b = dr.textbbox((x, y), label, font=f, anchor="mm")
        dr.rounded_rectangle((b[0] - 10, b[1] - 6, b[2] + 10, b[3] + 6), 8, fill=(43, 39, 35))
        dr.text((x, y), label, font=f, fill=(255, 248, 232), anchor="mm")
    im.resize((2000, round(im.height * 2000 / im.width))).save(d / f"{n}_named.jpg", quality=90)
    print("labelled", n)
