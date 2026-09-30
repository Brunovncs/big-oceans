"""Compare a lab grid (step 16, centred on a chunk-aligned point) with real chunks extracted by regions.py.

Usage: python validate.py <lab.json> <regions.npz>
Real OCEAN_FLOOR heights include features (trees, etc.) and carvers, so exact height equality is not expected;
the water/land split and the surface biome should match almost everywhere.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from analyze import load  # noqa: E402

meta, height, biome, _ = load(Path(sys.argv[1]))
job = meta["job"]
assert job["step"] == 16, "use step 16 so every sample is at local (8, 8) of a chunk"
r = dict(np.load(sys.argv[2]))  # materialise once: NpzFile decompresses on every item access
sea = meta["sea_level"]
x0 = job.get("cx", 0) - job["radius"]
z0 = job.get("cz", 0) - job["radius"]
names = list(r["names"])
pal = meta["palette"]
idx = {(int(x), int(z)): i for i, (x, z) in enumerate(zip(r["x"], r["z"]))}
n = meta["n"]
pairs = []
for j in range(n):
    for i in range(n):
        bx, bz = x0 + i * 16 + 8, z0 + j * 16 + 8
        k = idx.get((bx >> 4, bz >> 4))
        if k is None:
            continue
        pairs.append((height[j, i], r["height"][k][8, 8], pal[biome[j, i]], names[r["biome"][k][2, 2]]))
lab_h = np.array([p[0] for p in pairs])
real_h = np.array([p[1] for p in pairs])
water_agree = ((lab_h < sea) == (real_h < sea)).mean()
biome_agree = np.mean([p[2] == p[3] for p in pairs])
ocean_lab = np.array(["ocean" in p[2] for p in pairs])
ocean_real = np.array(["ocean" in p[3] for p in pairs])
print(json.dumps({
    "samples": len(pairs),
    "water_land_agreement_pct": round(100 * water_agree, 2),
    "ocean_biome_agreement_pct": round(100 * (ocean_lab == ocean_real).mean(), 2),
    "exact_biome_agreement_pct": round(100 * biome_agree, 2),
    "height_abs_diff_median": float(np.median(np.abs(lab_h - real_h))),
    "lab_ocean_pct": round(100 * ocean_lab.mean(), 2),
    "real_ocean_pct": round(100 * ocean_real.mean(), 2),
}, indent=1))
