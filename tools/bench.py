"""Chunk-generation benchmark: vanilla vs Big Oceans on a real server, same seeds and region.

Usage: python bench.py <loader> <out.json> seed:x:z [seed:x:z ...] [--extra a.jar ...]
Pregenerates a 129x129-chunk square centred on (x, z) with Chunky, once per configuration and seed, and keeps the
region files for validate.py. Pick centres outside the spawn fade where Big Oceans has ~50% land, otherwise the
comparison is skewed by open ocean being cheaper to generate.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
loader, out = sys.argv[1], Path(sys.argv[2])
args = sys.argv[3:]
extra = args[args.index("--extra") + 1:] if "--extra" in args else []
targets = [a.split(":") for a in (args[:args.index("--extra")] if extra else args)]
srv = ROOT / "build" / "servers" / loader
mods = ROOT / "build" / "testmods" / loader
jar = next((ROOT / loader / "build" / "libs").glob("big_oceans-*[0-9].jar"))
base = [str(mods / "chunky.jar")] + ([str(mods / "fabric-api.jar")] if loader == "fabric" else [])
base += extra
configs = {"vanilla": base, "big_oceans": base + [str(jar)]}
tag = "_".join(Path(e).stem for e in extra)
results = []
for seed, x, z in targets:
    for name, modlist in configs.items():
        r = subprocess.run([PY, str(ROOT / "tools" / "server.py"), "run", str(srv), seed, f"--pregen={x},{z},1024",
                            "--mods", *modlist], capture_output=True, text=True)
        res = json.loads(r.stdout[r.stdout.index("{"):])
        res["config"] = name
        res["center"] = [int(x), int(z)]
        results.append(res)
        print(name, seed, res.get("startup_s"), res.get("pregen_s"), res.get("chunks_per_s"), len(res["errors"]), flush=True)
        dst = ROOT / "build" / "bench" / loader / f"{name}{'_' + tag if tag else ''}_s{seed}"
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(srv / "world" / "region", dst / "region")
        out.write_text(json.dumps(results, indent=1))
