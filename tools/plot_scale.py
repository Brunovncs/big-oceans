"""Scale curve figure for the docs: python plot_scale.py <_stats.json> <out.png>

Means per variant (vanilla = scale 1.0, x15 = 1.5, ...). Left panel: typical crossing; right panel: coverage and
land integrity, all in percent, so each panel keeps a single y-axis.
"""
import collections
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

rows = json.load(open(sys.argv[1]))
groups = collections.defaultdict(list)
for r in rows:
    groups[r["name"].rsplit("_s", 1)[0]].append(r)


def scale_of(name):
    return 1.0 if name == "vanilla" else float(name[1:]) / (10 if len(name) > 2 else 1)


pts = sorted((scale_of(k), v) for k, v in groups.items())
xs = np.array([p[0] for p in pts])


def mean(key):
    return np.array([np.mean([r[key] for r in rs]) for _, rs in pts])


plt.rcParams.update({"font.size": 10, "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2,
                     "ytick.color": INK2, "text.color": INK})
fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.2), facecolor=SURFACE)
for ax in (a, b):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.axvline(4.0, color=INK2, lw=1, ls=(0, (3, 3)))
    ax.set_xlabel("ocean_scale")
    ax.set_xticks([1, 2, 3, 4, 5, 6, 7, 8])

cross = mean("chord_weighted_median") / 1000
a.plot(xs, cross, color=BLUE, lw=2, marker="o", ms=6, mec=SURFACE, mew=1.5)
for x, y in zip(xs, cross):
    if x in (1.0, 2.0, 3.0, 4.0, 6.0, 8.0):
        left = x == 3.0
        a.annotate(f"{y:.1f} km ({y / cross[0]:.1f}×)", (x, y), textcoords="offset points",
                   xytext=(-8, 4) if left else (6, -12), ha="right" if left else "left", fontsize=8.5, color=INK2)
a.set_ylabel("typical ocean crossing (km)")
a.set_ylim(0, cross.max() * 1.15)
a.set_title("Typical crossing (length-weighted median chord)", fontsize=10.5, loc="left")
a.text(4.08, cross.max() * 1.08, "default", fontsize=8.5, color=INK2)

for key, color, label in (("ocean_pct", BLUE, "ocean coverage"), ("deep_pct", ORANGE, "deep ocean coverage"),
                          ("land_share_mass_gt100_pct", AQUA, "land in masses > 100 km²")):
    y = mean(key)
    b.plot(xs, y, color=color, lw=2, marker="o", ms=6, mec=SURFACE, mew=1.5, label=label)
    b.annotate(label, (xs[-1], y[-1]), textcoords="offset points", xytext=(-4, 8), ha="right", fontsize=8.5,
               color=INK2)
b.set_ylabel("% of area / % of land")
b.set_ylim(0, 105)
b.set_title("Coverage and land integrity", fontsize=10.5, loc="left")
b.legend(frameon=False, fontsize=8.5, loc="lower right")

n = len(pts[0][1])
fig.text(0.01, 0.01, f"Mean of {n} seeds per scale, 49 × 49 km each, sampled from the real generator (Minecraft 1.21.1).",
         fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(sys.argv[2], dpi=130, facecolor=SURFACE)
print("wrote", sys.argv[2])
