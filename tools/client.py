"""Launch a real (production) 1.21.1 client for compatibility tests, via portablemc, with an offline account.

Usage: python client.py <fabric|quilt|neoforge|vanilla> <work-dir> (--world NAME | --server HOST:PORT)
                        [--mods a.jar ...] [--seconds 180] [--shots 3]

Installs the game into build/client/mc (shared), replaces <work-dir>/mods with the given jars, quick-plays straight
into the singleplayer world or server, takes in-game screenshots (F2) into <work-dir>/screenshots at even intervals,
then kills the game and prints a JSON summary (errors and crash reports from the log). The window must stay open
(not minimised) while it runs.
"""
import argparse
import ctypes
import ctypes.wintypes
import json
import re
import shutil
import time
from pathlib import Path

import truststore

truststore.inject_into_ssl()  # use the Windows certificate store; Python's bundled CAs reject some Maven hosts

from portablemc.fabric import FabricVersion  # noqa: E402
from portablemc.forge import _NeoForgeVersion as NeoForgeVersion  # noqa: E402 (still private in portablemc 4.x)
from portablemc.standard import Context, StandardRunner, Version  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
JAVA = Path.home() / ".jdks/jdk-21.0.12.1+1/bin/javaw.exe"
MC, FABRIC_LOADER, QUILT_LOADER, NEOFORGE = "1.21.1", "0.19.5", "0.30.1", "21.1.252"
user32 = ctypes.windll.user32


def minecraft_window(pid_hint=None):
    found = []

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value.startswith("Minecraft"):
                found.append(hwnd)
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(cb), 0)
    return found[0] if found else None


def screenshot(_path):
    """Presses F2 in the game window (PostMessage, so focus is not needed); the game saves <work>/screenshots/*.png."""
    hwnd = minecraft_window()
    if not hwnd:
        return False
    scan = 0x3C  # F2
    user32.PostMessageW(hwnd, 0x0100, 0x71, 1 | scan << 16)
    time.sleep(0.1)
    user32.PostMessageW(hwnd, 0x0101, 0x71, 1 | scan << 16 | 1 << 30 | 1 << 31)
    return True


class TimedRunner(StandardRunner):
    def __init__(self, seconds, shots, shot_dir):
        self.seconds, self.shots, self.shot_dir = seconds, shots, shot_dir
        self.taken = []

    def process_wait(self, process):
        start = time.time()
        marks = [start + self.seconds * (i + 1) / (self.shots + 1) for i in range(self.shots)]
        try:
            while process.poll() is None and time.time() - start < self.seconds:
                if marks and time.time() >= marks[0]:
                    marks.pop(0)
                    p = self.shot_dir / f"shot{len(self.taken) + 1}.png"
                    if screenshot(p):
                        self.taken.append(str(p))
                time.sleep(1)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("loader", choices=["fabric", "quilt", "neoforge", "vanilla"])
    ap.add_argument("work")
    ap.add_argument("--world")
    ap.add_argument("--server")
    ap.add_argument("--mods", nargs="*", default=[])
    ap.add_argument("--seconds", type=int, default=180)
    ap.add_argument("--shots", type=int, default=3)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(work / "mods", ignore_errors=True)
    (work / "mods").mkdir()
    for m in a.mods:
        shutil.copy(m, work / "mods" / Path(m).name)
    shots = work / "screenshots"
    shots.mkdir(exist_ok=True)
    before = set(shots.glob("*.png"))
    opts = work / "options.txt"
    if not opts.exists():
        opts.write_text("pauseOnLostFocus:false\nonboardAccessibility:false\nrenderDistance:12\ntutorialStep:none\n"
                        "skipMultiplayerWarning:true\njoinedFirstServer:true\n")
    ctx = Context(ROOT / "build" / "client" / "mc", work)
    if a.loader == "fabric":
        v = FabricVersion.with_fabric(MC, FABRIC_LOADER, context=ctx)
    elif a.loader == "quilt":
        v = FabricVersion.with_quilt(MC, QUILT_LOADER, context=ctx)
    elif a.loader == "neoforge":
        v = NeoForgeVersion(NEOFORGE, context=ctx)
    else:
        v = Version(MC, context=ctx)
    v.set_auth_offline("clientcheck", None)
    v.jvm_path = JAVA
    if a.world:
        v.set_quick_play_singleplayer(a.world)
    elif a.server:
        host, port = a.server.split(":")
        v.set_quick_play_multiplayer(host, int(port))
    env = v.install()
    env.jvm_args = [x for x in env.jvm_args if not x.startswith("-Xmx")] + ["-Xmx4G"]
    log = work / "logs" / "latest.log"
    if log.exists():
        log.unlink()
    runner = TimedRunner(a.seconds, a.shots, shots)
    t0 = time.time()
    env.run(runner)
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    lines = text.splitlines()
    print(json.dumps({
        "loader": a.loader, "work": str(work), "mods": [Path(m).name for m in a.mods], "ran_s": round(time.time() - t0),
        "joined": bool(re.search(r"joined the game|Connecting to|Started \d+ worker threads|logged in with entity id", text)),
        "screenshots": sorted(str(p) for p in set(shots.glob("*.png")) - before),
        "errors": [l[:300] for l in lines if re.search(r"/ERROR\]|/FATAL\]|Exception", l)][:25],
        "crash_reports": sorted(str(p) for p in (work / "crash-reports").glob("*.txt")) if (work / "crash-reports").exists() else [],
        "big_oceans_log": [l[:300] for l in lines if "Big Oceans" in l][:5],
    }, indent=1))


if __name__ == "__main__":
    main()
