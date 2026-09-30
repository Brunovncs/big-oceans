"""Tile several lab map PNGs into one labelled image: python montage.py out.png a.png b.png ..."""
import sys
from PIL import Image, ImageDraw
out, paths = sys.argv[1], sys.argv[2:]
ims = [Image.open(p) for p in paths]
w, h = ims[0].size
cols = min(len(ims), 3)
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (w + 4), rows * (h + 18)), "white")
d = ImageDraw.Draw(sheet)
for i, (p, im) in enumerate(zip(paths, ims)):
    x, y = (i % cols) * (w + 4), (i // cols) * (h + 18)
    sheet.paste(im, (x, y + 16))
    d.text((x + 2, y + 2), p.replace("\\", "/").split("/")[-1][:-4], fill="black")
sheet.save(out)
