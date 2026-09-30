"""Structure check on a real server: /locate common structures from several points, vanilla vs Big Oceans.

Usage: python structures.py <loader> <out.json> <seed> [<seed> ...]
Points are outside the spawn fade (> 2560 blocks from the origin), where Big Oceans changes the geography. Reports
the distance to the nearest structure of each type, or null when /locate found none within its search radius.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
STRUCTURES = ["village_plains", "village_desert", "village_taiga", "village_savanna", "monument", "shipwreck",
              "ocean_ruin_cold", "ocean_ruin_warm", "ruined_portal_ocean", "stronghold", "mansion", "pillager_outpost",
              "desert_pyramid", "jungle_pyramid", "swamp_hut", "igloo", "trail_ruins", "trial_chambers", "ancient_city",
              "buried_treasure"]
POINTS = [(6000, 6000), (-6000, 4000), (4000, -7000), (-8000, -8000)]
FOUND = re.compile(r"The nearest minecraft:(\w+) is at \[(-?\d+), [^,]+, (-?\d+)\] \((\d+) blocks away\)")
MISSING = re.compile(r"Could not find a structure of type \"?minecraft:(\w+)")


def main():
    loader, out, seeds = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]
    srv = ROOT / "build" / "servers" / loader
    mods = ROOT / "build" / "testmods" / loader
    jar = next((ROOT / loader / "build" / "libs").glob("big_oceans-*[0-9].jar"))
    base = [str(mods / "fabric-api.jar")] if loader in ("fabric", "quilt") else []
    cmds = [f"execute positioned {x} 64 {z} run locate structure minecraft:{s}" for x, z in POINTS for s in STRUCTURES]
    results = []
    for seed in seeds:
        for name, modlist in (("vanilla", base), ("big_oceans", base + [str(jar)])):
            args = [PY, str(ROOT / "tools" / "server.py"), "run", str(srv), seed, "--timeout", "900", "--mods", *modlist]
            for c in cmds:
                args += ["--cmd", c]
            r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
            res = json.loads(r.stdout[r.stdout.index("{"):])
            log = (srv / "last_run.log").read_text(encoding="utf-8", errors="replace").splitlines()
            answers = [l for l in log if FOUND.search(l) or MISSING.search(l)]
            table = {}
            for (x, z), line in zip([p for p in POINTS for _ in STRUCTURES], answers):
                m = FOUND.search(line)
                if m:
                    table.setdefault(m.group(1), []).append(int(m.group(4)))
                else:
                    table.setdefault(MISSING.search(line).group(1), []).append(None)
            results.append({"seed": seed, "config": name, "answers": len(answers), "expected": len(cmds),
                            "errors": res.get("errors", []), "distances": table})
            print(seed, name, len(answers), "/", len(cmds), "errors", len(res.get("errors", [])), flush=True)
            out.write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
