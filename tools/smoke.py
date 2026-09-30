"""Smoke test of the built jars on every supported Minecraft line: python smoke.py <dist-dir> <out.json>

For each versions/<mc>.properties: installs a real Fabric and NeoForge server (once, into build/servers/v/), starts
it with the matching Big Oceans jar from <dist-dir>, force-loads 15 x 15 chunks of seed 5 around (-7818, -1162),
stops it and reports errors, whether the mod was active, and the water share of the saved chunks. The worldgen data
Big Oceans builds on is the same on all these versions, so the water share should match 1.21.1's.
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import server  # noqa: E402  (also installs the system trust store)

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
FORCELOAD = "forceload add -7936 -1280 -7700 -1044"


def props(mc):
    out = {}
    for line in (ROOT / "versions" / f"{mc}.properties").read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def water(world):
    npz = world.parent / "smoke.npz"
    subprocess.run([PY, str(ROOT / "tools" / "regions.py"), str(world), str(npz)], check=True, capture_output=True)
    h = np.load(npz)["height"]
    return round(100 * float((h < 63).mean()), 2), len(h)


def main():
    dist, out = Path(sys.argv[1]), Path(sys.argv[2])
    results = []
    for f in sorted((ROOT / "versions").glob("*.properties"), key=lambda p: [int(x) for x in p.stem.split(".")]):
        mc = f.stem
        p = props(mc)
        for loader in ("fabric", "neoforge"):
            d = ROOT / "build" / "servers" / "v" / f"{mc}-{loader}"
            if not (d / "launch.json").exists():
                server.setup(loader, d, p["minecraft_version"], p["neoforge_version"])
            jar = next(dist.glob(f"big_oceans-{loader}-*+{p['jar_label']}.jar"))
            mods = [str(jar)]
            if loader == "fabric":
                api = ROOT / "build" / "testmods" / "fabric-api" / f"fabric-api-{p['fabric_api_version']}.jar"
                if not api.exists():
                    api.parent.mkdir(parents=True, exist_ok=True)
                    v = p["fabric_api_version"]
                    urllib.request.urlretrieve(
                        f"https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/{v}/fabric-api-{v}.jar", api)
                mods.append(str(api))
            cmds = ["--cmd", FORCELOAD] + ["--cmd", "list"] * 40
            r = subprocess.run([PY, str(ROOT / "tools" / "server.py"), "run", str(d), "5", "--timeout", "900", "--mods",
                                *mods, *cmds], capture_output=True, text=True, encoding="utf-8", errors="replace")
            try:
                res = json.loads(r.stdout[r.stdout.index("{"):])
            except ValueError:
                res = {"started": False, "stderr": r.stderr[-1500:]}
            row = {"mc": mc, "loader": loader, "jar": jar.name, "started": res.get("started"),
                   "crashed": res.get("crashed"), "errors": res.get("errors", []),
                   "active": any("active" in l for l in res.get("big_oceans_log", []))}
            if res.get("started") and (d / "world" / "region").is_dir():
                row["water_pct"], row["chunks"] = water(d / "world")
            results.append(row)
            print(mc, loader, row["started"], row["active"], row.get("water_pct"), row.get("chunks"), len(row["errors"]),
                  flush=True)
            out.write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
