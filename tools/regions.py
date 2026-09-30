"""Minimal Anvil reader: extracts per-column surface data from real generated chunks (region/*.mca).

Produces, for every fully generated chunk, the OCEAN_FLOOR heightmap and the surface biome of each 4x4 column, so
lab predictions can be checked against what the game actually saved.

Usage: python regions.py <world-dir> <out.npz>
"""
import struct
import sys
import zlib
from pathlib import Path

import numpy as np


class Reader:
    def __init__(self, data):
        self.d, self.p = data, 0

    def take(self, n):
        v = self.d[self.p:self.p + n]
        self.p += n
        return v

    def u(self, fmt):
        size = struct.calcsize(fmt)
        v = struct.unpack(">" + fmt, self.d[self.p:self.p + size])[0]
        self.p += size
        return v

    def string(self):
        return self.take(self.u("H")).decode("utf-8", "replace")

    def payload(self, tag):
        if tag == 1: return self.u("b")
        if tag == 2: return self.u("h")
        if tag == 3: return self.u("i")
        if tag == 4: return self.u("q")
        if tag == 5: return self.u("f")
        if tag == 6: return self.u("d")
        if tag == 7: return self.take(self.u("i"))
        if tag == 8: return self.string()
        if tag == 9:
            t, n = self.u("b"), self.u("i")
            return [self.payload(t) for _ in range(n)]
        if tag == 10:
            out = {}
            while True:
                t = self.u("b")
                if t == 0:
                    return out
                name = self.string()
                out[name] = self.payload(t)
        if tag == 11:
            n = self.u("i")
            return np.frombuffer(self.take(4 * n), ">i4")
        if tag == 12:
            n = self.u("i")
            return np.frombuffer(self.take(8 * n), ">i8")
        raise ValueError(f"bad tag {tag}")


def read_nbt(data):
    r = Reader(data)
    t = r.u("b")
    r.string()
    return r.payload(t)


def unpack(longs, bits, count):
    """Unpack values that do not span longs (the 1.16+ layout)."""
    per = 64 // bits
    mask = (1 << bits) - 1
    u = longs.astype(np.uint64)
    out = np.empty(len(u) * per, np.int64)
    for i in range(per):
        out[i::per] = ((u >> np.uint64(i * bits)) & np.uint64(mask)).astype(np.int64)
    return out[:count]


def chunks(world):
    for mca in sorted((Path(world) / "region").glob("r.*.mca")):
        raw = mca.read_bytes()
        if len(raw) < 8192:
            continue
        for i in range(1024):
            off = int.from_bytes(raw[4 * i:4 * i + 3], "big")
            if off == 0:
                continue
            start = off * 4096
            length = int.from_bytes(raw[start:start + 4], "big")
            comp = raw[start + 4]
            body = raw[start + 5:start + 4 + length]
            if comp == 2:
                body = zlib.decompress(body)
            elif comp == 1:
                import gzip
                body = gzip.decompress(body)
            else:
                continue
            yield read_nbt(body)


def main():
    world, out = sys.argv[1], sys.argv[2]
    xs, zs, heights, biomes = [], [], [], []
    names = {}
    for c in chunks(world):
        if c.get("Status") != "minecraft:full":
            continue
        hm = c.get("Heightmaps", {}).get("OCEAN_FLOOR")
        if hm is None:
            continue
        h = unpack(hm, 9, 256) - 64  # stored relative to min build height (-64)
        cx, cz = c["xPos"], c["zPos"]
        # Surface biome per 4x4 column: take the biome of the section containing y = max(h, sea level).
        sections = {s["Y"]: s for s in c["sections"] if "biomes" in s}
        bgrid = np.zeros((4, 4), np.int32)
        for qz in range(4):
            for qx in range(4):
                y = max(int(h[(qz * 4) * 16 + qx * 4]), 63)
                s = sections.get(y >> 4)
                if s is None:
                    continue
                pal = s["biomes"]["palette"]
                if len(pal) == 1:
                    name = pal[0]
                else:
                    bits = max(1, (len(pal) - 1).bit_length())
                    idx = unpack(s["biomes"]["data"], bits, 64)
                    qy = (y & 15) >> 2
                    name = pal[int(idx[(qy * 4 + qz) * 4 + qx])]
                bgrid[qz, qx] = names.setdefault(name, len(names))
        xs.append(cx)
        zs.append(cz)
        heights.append(h.reshape(16, 16))
        biomes.append(bgrid)
    np.savez_compressed(out, x=np.array(xs), z=np.array(zs), height=np.array(heights), biome=np.array(biomes),
                        names=np.array(sorted(names, key=names.get)))
    print(f"{len(xs)} full chunks, {len(names)} surface biomes")


if __name__ == "__main__":
    main()
