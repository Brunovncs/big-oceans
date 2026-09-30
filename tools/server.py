"""Drive real (non-dev) Minecraft servers for benchmarks and compatibility tests.

  python server.py setup <loader> <dir>                 install a Fabric/NeoForge/Quilt 1.21.1 server into <dir>
  python server.py run <dir> <seed> [--mods a.jar ...] [--pregen X,Z,R] [--cmd "..."] [--scale S] [--keep-world]

`run` wipes the world (unless --keep-world), copies the given mods, starts the server, optionally runs a Chunky
pregeneration centred on X,Z with radius R blocks, runs extra console commands, stops the server and prints a JSON
summary (startup time, pregen time/chunk rate, errors found in the log).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

JAVA = str(Path.home() / ".jdks/jdk-21.0.12.1+1/bin/java.exe")
MC = "1.21.1"
FABRIC_LOADER = "0.19.5"
NEOFORGE = "21.1.252"
QUILT_INSTALLER = "0.15.1"


def setup(loader, d: Path):
    d.mkdir(parents=True, exist_ok=True)
    if loader == "fabric":
        url = f"https://meta.fabricmc.net/v2/versions/loader/{MC}/{FABRIC_LOADER}/1.1.0/server/jar"
        urllib.request.urlretrieve(url, d / "server.jar")
        (d / "launch.json").write_text(json.dumps({"cmd": [JAVA, "-Xmx6G", "-jar", "server.jar", "nogui"]}))
        # First start downloads the vanilla server and libraries, then exits because of the EULA.
        subprocess.run([JAVA, "-jar", "server.jar", "nogui"], cwd=d, stdout=subprocess.DEVNULL, timeout=600)
    elif loader == "quilt":
        inst = d / "quilt-installer.jar"
        urllib.request.urlretrieve("https://maven.quiltmc.org/repository/release/org/quiltmc/quilt-installer/"
                                   f"{QUILT_INSTALLER}/quilt-installer-{QUILT_INSTALLER}.jar", inst)
        subprocess.run([JAVA, "-jar", str(inst), "install", "server", MC, "--download-server", "--install-dir=."],
                       cwd=d, check=True, stdout=subprocess.DEVNULL)
        (d / "launch.json").write_text(json.dumps({"cmd": [JAVA, "-Xmx6G", "-jar", "quilt-server-launch.jar", "nogui"]}))
    else:
        inst = d / "installer.jar"
        urllib.request.urlretrieve(
            f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{NEOFORGE}/neoforge-{NEOFORGE}-installer.jar", inst)
        subprocess.run([JAVA, "-jar", str(inst), "--installServer"], cwd=d, check=True, stdout=subprocess.DEVNULL)
        args = f"@libraries/net/neoforged/neoforge/{NEOFORGE}/win_args.txt"
        (d / "launch.json").write_text(json.dumps({"cmd": [JAVA, "-Xmx6G", args, "nogui"]}))
    (d / "eula.txt").write_text("eula=true\n")
    print("installed", loader, d)


def run(d: Path, seed, mods, pregen, cmds, scale, keep_world, timeout, port=25599):
    if not keep_world:
        shutil.rmtree(d / "world", ignore_errors=True)
    shutil.rmtree(d / "mods", ignore_errors=True)
    (d / "mods").mkdir()
    for m in mods:
        shutil.copy(m, d / "mods" / Path(m).name)
    (d / "config").mkdir(exist_ok=True)
    if scale is not None:
        (d / "config" / "big_oceans.toml").write_text(f"ocean_scale = {scale}\n")
    (d / "server.properties").write_text(
        f"level-seed={seed}\nonline-mode=false\nview-distance=6\nsimulation-distance=6\nspawn-protection=0\n"
        f"max-tick-time=-1\nsync-chunk-writes=false\nserver-port={port}\n")
    cmd = json.loads((d / "launch.json").read_text())["cmd"]
    log_lines = []
    p = subprocess.Popen(cmd, cwd=d, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace", bufsize=1)
    events = {}

    def reader():
        for line in p.stdout:
            log_lines.append(line)
            now = time.time()
            if "Done (" in line and "done" not in events:
                events["done"] = now
            if "[Chunky] Task finished" in line or re.search(r"Task finished for", line):
                events["pregen_done"] = now
            if "[Chunky] Task started" in line or "Task started for" in line:
                events["pregen_start"] = now
            if "This crash report has been saved to" in line or "Encountered an unexpected exception" in line:
                events.setdefault("crashed", now)

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    t0 = time.time()

    def send(s):
        p.stdin.write(s + "\n")
        p.stdin.flush()

    def wait(key, limit):
        end = time.time() + limit
        while key not in events and "crashed" not in events and time.time() < end and p.poll() is None:
            time.sleep(0.2)
        return key in events

    ok = wait("done", timeout)
    result = {"dir": str(d), "seed": seed, "mods": [Path(m).name for m in mods], "started": ok}
    if ok:
        result["startup_s"] = round(events["done"] - t0, 2)
        for c in cmds:
            send(c)
            time.sleep(1.5)
        if pregen:
            x, z, r = pregen.split(",")
            send(f"chunky world minecraft:overworld")
            send(f"chunky center {x} {z}")
            send(f"chunky radius {r}")
            send("chunky shape square")
            send("chunky start")
            if wait("pregen_done", timeout):
                result["pregen_s"] = round(events["pregen_done"] - events.get("pregen_start", events["done"]), 2)
                chunks = (2 * int(r) // 16 + 1) ** 2
                result["pregen_chunks"] = chunks
                result["chunks_per_s"] = round(chunks / result["pregen_s"], 1)
            else:
                result["pregen_s"] = None
        send("stop")
    try:
        p.wait(120)
    except subprocess.TimeoutExpired:
        p.kill()
    text = "".join(log_lines)
    (d / "last_run.log").write_text(text, encoding="utf-8")
    result["exit_code"] = p.returncode
    result["crashed"] = "crashed" in events
    result["errors"] = [l.strip()[:300] for l in log_lines if re.search(r"/ERROR\]|Exception|FATAL", l)][:20]
    result["big_oceans_log"] = [l.strip()[:300] for l in log_lines if "Big Oceans" in l][:5]
    print(json.dumps(result, indent=1))
    return result


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="op", required=True)
    s = sub.add_parser("setup")
    s.add_argument("loader", choices=["fabric", "neoforge", "quilt"])
    s.add_argument("dir")
    r = sub.add_parser("run")
    r.add_argument("dir")
    r.add_argument("seed")
    r.add_argument("--mods", nargs="*", default=[])
    r.add_argument("--pregen")
    r.add_argument("--cmd", action="append", default=[])
    r.add_argument("--scale", type=float)
    r.add_argument("--keep-world", action="store_true")
    r.add_argument("--timeout", type=int, default=3600)
    r.add_argument("--port", type=int, default=25599)
    a = ap.parse_args()
    if a.op == "setup":
        setup(a.loader, Path(a.dir))
    else:
        run(Path(a.dir), a.seed, a.mods, a.pregen, a.cmd, a.scale, a.keep_world, a.timeout, a.port)


if __name__ == "__main__":
    sys.exit(main())
