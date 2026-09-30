"""Compatibility check on a real server: does Big Oceans still work, unchanged, next to another mod?

Usage: python compat.py <loader> <out.json> <seed:x:z> <name>=<jar>[,<jar>...] [<name>=...]
       (a name may map to "-" for no extra mods; the jar list may include the Big Oceans jar or not)

For every configuration: wipes the world, pregenerates a 65x65-chunk square centred on (x, z) with Chunky, extracts
the saved chunks with regions.py and reports errors, pregen time, ocean share and how many columns have exactly the
same OCEAN_FLOOR height as the first configuration (the reference, normally Big Oceans alone). An optimisation mod
that preserves vanilla worldgen should give ~100% identical columns; a worldgen mod shows how the two combine.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
RADIUS = 512


def columns(npz):
    r = np.load(npz)
    return {(int(x), int(z)): h for x, z, h in zip(r["x"], r["z"], r["height"])}


def main():
    loader, out, target = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    seed, x, z = target.split(":")
    srv = ROOT / "build" / "servers" / loader
    mods_dir = ROOT / "build" / "testmods" / loader
    base = [str(mods_dir / "chunky.jar")] + ([str(mods_dir / "fabric-api.jar")] if loader in ("fabric", "quilt") else [])
    results, ref = [], None
    for spec in sys.argv[4:]:
        name, jars = spec.split("=", 1)
        mods = base + ([j for j in jars.split(",") if j] if jars != "-" else [])
        r = subprocess.run([PY, str(ROOT / "tools" / "server.py"), "run", str(srv), seed, f"--pregen={x},{z},{RADIUS}",
                            "--mods", *mods], capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            res = json.loads(r.stdout[r.stdout.index("{"):])
        except ValueError:
            res = {"started": False, "stdout_tail": r.stdout[-2000:], "stderr_tail": r.stderr[-2000:]}
        res["config"] = name
        dst = ROOT / "build" / "compat" / loader / name
        shutil.rmtree(dst, ignore_errors=True)
        region = srv / "world" / "region"
        if res.get("pregen_s") and region.is_dir():
            shutil.copytree(region, dst / "region")
            npz = dst.with_suffix(".npz")
            subprocess.run([PY, str(ROOT / "tools" / "regions.py"), str(dst), str(npz)], check=True, capture_output=True)
            cols = columns(npz)
            h = np.stack(list(cols.values()))
            res["chunks_saved"] = len(cols)
            res["ocean_pct"] = round(100 * float((h < 63).mean()), 2)
            if ref is None:
                ref = cols
            else:
                common = [k for k in cols if k in ref]
                same = np.mean([np.array_equal(cols[k], ref[k]) for k in common]) if common else 0.0
                res["identical_chunks_vs_ref_pct"] = round(100 * float(same), 2)
                res["identical_columns_vs_ref_pct"] = round(
                    100 * float(np.mean([(cols[k] == ref[k]).mean() for k in common])) if common else 0.0, 2)
        results.append(res)
        print(name, res.get("started"), res.get("pregen_s"), res.get("ocean_pct"),
              res.get("identical_columns_vs_ref_pct"), len(res.get("errors", [])), flush=True)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
