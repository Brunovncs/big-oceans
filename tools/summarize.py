"""Mean of key metrics per variant (name prefix before _s<seed>) from an analyze.py _stats.json."""
import collections, json, sys
import numpy as np
rows = json.load(open(sys.argv[1]))
g = collections.defaultdict(list)
for r in rows:
    g[r["name"].rsplit("_s", 1)[0]].append(r)
keys = ["ocean_pct", "deep_pct", "chord_weighted_median", "chord_p95", "dist_to_land_p90", "dist_to_land_max",
        "ocean_farther_512_pct", "land_share_mass_gt100_pct", "land_share_islet_lt1_pct", "landmass_count_per_1000km2", "ocean_largest_share_pct", "landmass_count_gt100km2",
        "coast_km_per_km2", "beach_width", "land_above_120_pct", "biome_js", "mushroom_pct"]
short = ["ocean%", "deep%", "crossW50", "chordP95", "dLandP90", "dLandMax", "far512%", "land>100", "islet%", "masses/k", "oceConn%", "n>100km2",
         "coast", "beachW", "hi120%", "biomeJS", "mush%"]
print("variant".ljust(9) + "".join(s.rjust(9) for s in short) + "  spawnLand")
for v, rs in g.items():
    print(v.ljust(9) + "".join(f"{np.mean([r[k] for r in rs]):9.{3 if k == 'biome_js' else 1}f}" for k in keys)
          + f"  {sum(r['spawn_on_land'] for r in rs)}/{len(rs)}")
