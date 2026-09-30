"""Analyse Big Oceans lab grids: ocean/land classification, geography statistics and top-down maps.

Usage: python analyze.py <lab-output-dir> [--maps] [--csv out.csv]
Each job produces <name>.bin (big-endian int16 heights, int16 biome ids, float32 continentalness) and <name>.json.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

DEEP_PREFIX = "minecraft:deep_"
LAND, BEACH, RIVER, OCEAN, DEEP, MUSHROOM = 0, 1, 2, 3, 4, 5


def load(json_path: Path):
    meta = json.loads(json_path.read_text())
    n = meta["n"]
    raw = json_path.with_suffix(".bin").read_bytes()
    k = n * n
    height = np.frombuffer(raw, ">i2", k, 0).reshape(n, n).astype(np.int32)
    biome = np.frombuffer(raw, ">i2", k, 2 * k).reshape(n, n)
    cont = np.frombuffer(raw, ">f4", k, 4 * k).reshape(n, n)
    return meta, height, biome, cont


def classify(meta, biome):
    lut = np.zeros(len(meta["palette"]), np.uint8)
    for i, name in enumerate(meta["palette"]):
        if name.endswith("ocean"):
            lut[i] = DEEP if name.startswith(DEEP_PREFIX) else OCEAN
        elif name.endswith("river"):
            lut[i] = RIVER
        elif name.endswith("beach") or name.endswith("shore"):
            lut[i] = BEACH
        elif name.endswith("mushroom_fields"):
            lut[i] = MUSHROOM
    return lut[biome]


def chords(mask):
    """Lengths (in cells) of maximal runs of True along rows and columns that do not touch the grid border."""
    out = []
    for m in (mask, mask.T):
        padded = np.pad(m.astype(np.int8), ((0, 0), (1, 1)))
        d = np.diff(padded, axis=1)
        for r in range(m.shape[0]):
            starts = np.flatnonzero(d[r] == 1)
            ends = np.flatnonzero(d[r] == -1)
            ok = (starts > 0) & (ends < m.shape[1])
            out.append(ends[ok] - starts[ok])
    return np.concatenate(out) if out else np.zeros(0, int)


def pct(a, q):
    return float(np.percentile(a, q)) if len(a) else 0.0


def stats(meta, height, biome):
    step = meta["job"]["step"]
    n = meta["n"]
    cls = classify(meta, biome)
    ocean = (cls == OCEAN) | (cls == DEEP)
    land = ~ocean
    cell_km2 = (step / 1000) ** 2
    s = {"name": meta["job"]["name"], "seed": meta["job"]["seed"], "variant": meta["job"]["variant"],
         "size_blocks": n * step, "step": step}
    s["ocean_pct"] = 100 * ocean.mean()
    s["deep_pct"] = 100 * (cls == DEEP).mean()
    s["water_surface_pct"] = 100 * (height < meta["sea_level"]).mean()
    s["mushroom_pct"] = 100 * (cls == MUSHROOM).mean()
    s["beach_pct"] = 100 * (cls == BEACH).mean()

    c = chords(ocean) * step
    s["chord_mean"] = float(c.mean()) if len(c) else 0
    s["chord_median"] = pct(c, 50)
    s["chord_p90"] = pct(c, 90)
    s["chord_p95"] = pct(c, 95)
    s["chord_max"] = float(c.max()) if len(c) else 0
    # Length-weighted median: the chord length a random point at sea lies on (what a sailor experiences).
    if len(c):
        order = np.sort(c)
        cw = np.cumsum(order) / order.sum()
        s["chord_weighted_median"] = float(order[np.searchsorted(cw, 0.5)])
    else:
        s["chord_weighted_median"] = 0

    dist = ndimage.distance_transform_edt(ocean) * step
    od = dist[ocean]
    s["dist_to_land_median"] = pct(od, 50)
    s["dist_to_land_p90"] = pct(od, 90)
    s["dist_to_land_max"] = float(od.max()) if len(od) else 0
    for r in (256, 512, 1000):
        s[f"ocean_farther_{r}_pct"] = 100 * (od > r).mean() if len(od) else 0

    lab, nl = ndimage.label(land)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    sizes = ndimage.sum_labels(np.ones_like(lab), lab, np.arange(1, nl + 1)) * cell_km2
    interior = np.array([sizes[i] for i in range(nl) if (i + 1) not in border])
    s["landmass_count_per_1000km2"] = 1000 * len(sizes) / (n * n * cell_km2)
    s["landmass_largest_km2"] = float(sizes.max()) if nl else 0
    s["landmass_largest_share_pct"] = 100 * float(sizes.max()) / max(land.sum() * cell_km2, 1e-9) if nl else 0
    s["landmass_median_km2"] = pct(interior, 50)
    tot = land.sum() * cell_km2
    for lo, hi, key in ((0, 1, "islet_lt1"), (1, 10, "island_1_10"), (10, 100, "island_10_100"), (100, 1e12, "mass_gt100")):
        s[f"land_share_{key}_pct"] = 100 * sizes[(sizes >= lo) & (sizes < hi)].sum() / max(tot, 1e-9)

    olab, no = ndimage.label(ocean)
    osz = ndimage.sum_labels(np.ones_like(olab), olab, np.arange(1, no + 1)) if no else np.zeros(1)
    s["ocean_largest_share_pct"] = 100 * float(osz.max()) / max(ocean.sum(), 1)
    s["landmass_count_gt10km2"] = int((sizes >= 10).sum())
    s["landmass_count_gt100km2"] = int((sizes >= 100).sum())

    edges = (ocean[:, 1:] != ocean[:, :-1]).sum() + (ocean[1:] != ocean[:-1]).sum()
    s["coast_km_per_km2"] = edges * step / 1000 / (n * n * cell_km2)

    coast_blocks = max(edges * step, 1)
    s["beach_width"] = (cls == BEACH).sum() * step * step / coast_blocks
    lh = height[land & (cls != RIVER)]
    s["land_height_mean"] = float(lh.mean()) if len(lh) else 0
    s["land_above_120_pct"] = 100 * float((lh > 120).mean()) if len(lh) else 0
    s["land_above_160_pct"] = 100 * float((lh > 160).mean()) if len(lh) else 0
    names = meta["palette"]
    lb = biome[land & (cls != BEACH) & (cls != RIVER)]
    hist = np.bincount(lb, minlength=len(names)).astype(float)
    s["land_biomes"] = {names[i]: hist[i] / max(hist.sum(), 1) for i in range(len(names)) if hist[i] > 0}

    sp = meta["spawn"]
    s["spawn_dist"] = float(np.hypot(sp["x"], sp["z"]))
    s["spawn_on_land"] = sp["height"] >= meta["sea_level"]
    s["spawn_biome"] = sp["biome"]
    s["seconds"] = meta.get("seconds")
    return s, cls


def render(meta, height, cls, path):
    from PIL import Image
    sea = meta["sea_level"]
    img = np.zeros(height.shape + (3,), np.uint8)
    h = np.clip((height - sea) / 120.0, 0, 1)[..., None]
    land_lo, land_hi = np.array([86, 150, 70]), np.array([235, 235, 235])
    img[:] = (land_lo + (land_hi - land_lo) * h).astype(np.uint8)
    img[cls == BEACH] = (220, 205, 140)
    img[cls == RIVER] = (90, 150, 230)
    img[cls == MUSHROOM] = (170, 90, 190)
    depth = np.clip((sea - height) / 50.0, 0, 1)[..., None]
    shallow, deep = np.array([70, 130, 220]), np.array([10, 30, 110])
    ocean_px = (shallow + (deep - shallow) * depth).astype(np.uint8)
    om = (cls == OCEAN) | (cls == DEEP)
    img[om] = ocean_px[om]
    lake = (~om) & (height < sea) & (cls != RIVER)
    img[lake] = (60, 120, 200)
    Image.fromarray(img).save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--maps", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    d = Path(a.dir)
    rows = []
    for jp in sorted(d.glob("*.json")):
        if jp.name.startswith("_"):
            continue
        meta, height, biome, _ = load(jp)
        s, cls = stats(meta, height, biome)
        rows.append(s)
        if a.maps:
            render(meta, height, cls, jp.with_suffix(".png"))
    by_seed = {r["seed"]: r["land_biomes"] for r in rows if r["variant"]["family"] == "vanilla"}
    for r in rows:
        ref = by_seed.get(r["seed"])
        if ref is None:
            r["biome_js"] = float("nan")
            continue
        keys = set(ref) | set(r["land_biomes"])
        p = np.array([ref.get(k, 0) for k in keys]) + 1e-12
        q = np.array([r["land_biomes"].get(k, 0) for k in keys]) + 1e-12
        m = (p + q) / 2
        r["biome_js"] = float(0.5 * (p * np.log2(p / m)).sum() + 0.5 * (q * np.log2(q / m)).sum())
    out = Path(a.out) if a.out else d / "_stats.json"
    out.write_text(json.dumps(rows, indent=1, default=float))
    keys = ["name", "ocean_pct", "deep_pct", "chord_median", "chord_weighted_median", "chord_p95", "chord_max",
            "dist_to_land_p90", "dist_to_land_max", "landmass_largest_km2", "land_share_mass_gt100_pct",
            "land_share_islet_lt1_pct", "coast_km_per_km2", "beach_width", "land_height_mean", "land_above_120_pct",
            "biome_js", "mushroom_pct", "spawn_on_land"]
    print("\t".join(k[:14] for k in keys))
    for r in rows:
        print("\t".join((f"{r[k]:.3f}" if k == "biome_js" else f"{r[k]:.1f}") if isinstance(r[k], float) else str(r[k])
                        for k in keys))


if __name__ == "__main__":
    sys.exit(main())
