"""Regression check for the known seeds (tools/jobs/regression.json, run with :fabric:runLab).

Usage: python regression.py <lab-output-dir> [--update]
Analyses the grids and compares key metrics with tools/jobs/regression_baseline.json. Generation is deterministic, so
any difference beyond float noise means the worldgen output changed. --update rewrites the baseline.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "tools" / "jobs" / "regression_baseline.json"
KEYS = ["ocean_pct", "deep_pct", "chord_weighted_median", "dist_to_land_p90", "land_share_mass_gt100_pct",
        "landmass_largest_km2", "beach_width", "spawn_on_land"]
# Invariants that must hold whatever the baseline says (see the README).
CHECKS = {
    "x4": lambda r: 45 <= r["ocean_pct"] <= 70 and r["chord_weighted_median"] >= 2500 and r["land_share_mass_gt100_pct"] >= 30,
    "vanilla": lambda r: 25 <= r["ocean_pct"] <= 36,
}


def main():
    d = Path(sys.argv[1])
    subprocess.run([sys.executable, str(ROOT / "tools" / "analyze.py"), str(d)], check=True, capture_output=True)
    rows = {r["name"]: {k: r[k] for k in KEYS} for r in json.loads((d / "_stats.json").read_text())}
    if "--update" in sys.argv:
        BASELINE.write_text(json.dumps(rows, indent=1, default=float))
        print(f"baseline written: {len(rows)} jobs")
        return 0
    base = json.loads(BASELINE.read_text())
    failures = []
    for name, want in base.items():
        got = rows.get(name)
        if got is None:
            failures.append(f"{name}: missing")
            continue
        for k, v in want.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                ok = got[k] == v
            else:
                ok = abs(got[k] - v) <= 1e-6 * max(1.0, abs(v))
            if not ok:
                failures.append(f"{name}.{k}: baseline {v}, now {got[k]}")
        if not CHECKS[name.rsplit("_s", 1)[0]](got):
            failures.append(f"{name}: invariant violated {got}")
    for f in failures:
        print("FAIL", f)
    print(f"{len(base)} jobs, {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
