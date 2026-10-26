"""Rebuild Xbox texture containers using the texture IDs (header field 0x0C) of the matching PC slot.

Pixels and palettes stay from Xbox; only the per-texture ID is taken from PC, because the PC
game looks textures up by that ID and Xbox IDs are offset by one.
"""
import csv
import struct
import sys
import zlib
from pathlib import Path

TEX_MAGIC = b"\x94\x72\x85\x29"
BLOCK = b"\x00\x03\x01\x00"
BASE = 0x20


def reader(path):
    f = open(path, "rb")
    f.seek(4)
    n = struct.unpack("<I", f.read(4))[0]
    t = f.read(n * 8)

    def get(i):
        o, s = struct.unpack_from("<II", t, i * 8)
        f.seek(o)
        return f.read(s)
    return get


def blocks(container):
    count, _, data_tab = struct.unpack_from("<III", container, BASE)
    offs = [BASE + struct.unpack_from("<I", container, BASE + data_tab + 4 * k)[0] for k in range(count)]
    return count, data_tab, offs


def inflate_block(container, off):
    if container[off:off + 4] != BLOCK:
        return None
    csize = struct.unpack_from("<I", container, off + 4)[0]
    return zlib.decompress(container[off + 32:off + 32 + csize])


def deflate_block(raw):
    comp = zlib.compress(raw, 9)
    return BLOCK + struct.pack("<II", len(comp), len(raw)) + b"\x00" * 20 + comp


def patch_container(cx, cp):
    count_x, data_tab, offs_x = blocks(cx)
    count_p, _, offs_p = blocks(cp)
    if count_x != count_p:
        raise ValueError(f"distinta cantidad de texturas {count_x} vs {count_p}")
    out = bytearray(cx[:offs_x[0]])
    patched = 0
    for k in range(count_x):
        rx, rp = inflate_block(cx, offs_x[k]), inflate_block(cp, offs_p[k])
        if rx is None or rp is None:
            raise ValueError(f"bloque {k} sin formato esperado")
        if rx[:4] == TEX_MAGIC and rp[:4] == TEX_MAGIC and rx[0x0C:0x10] != rp[0x0C:0x10]:
            rx = rx[:0x0C] + rp[0x0C:0x10] + rx[0x10:]
            patched += 1
        while len(out) % 16:
            out.append(0)
        struct.pack_into("<I", out, BASE + data_tab + 4 * k, len(out) - BASE)
        out += deflate_block(rx)
    while len(out) % 16:
        out.append(0)
    struct.pack_into("<I", out, 4, len(out) - BASE)
    return bytes(out), patched


def verify(new, cx, cp):
    _, _, on = blocks(new)
    _, _, ox = blocks(cx)
    _, _, op = blocks(cp)
    for k in range(len(on)):
        rn, rx, rp = inflate_block(new, on[k]), inflate_block(cx, ox[k]), inflate_block(cp, op[k])
        if rn[0x0C:0x10] != rp[0x0C:0x10] or rn[:0x0C] != rx[:0x0C] or rn[0x10:] != rx[0x10:]:
            return False
    return True


def main(xbox_afs, pc_afs, safe_csv, pc_indices, out_dir):
    gx, gp = reader(xbox_afs), reader(pc_afs)
    wanted = {int(i) for i in pc_indices.split(",")}
    out = Path(out_dir) / Path(pc_afs).name
    out.mkdir(parents=True, exist_ok=True)
    for r in csv.DictReader(open(safe_csv, encoding="utf-8")):
        if r["kind"] != "safe" or int(r["pc_index"]) not in wanted:
            continue
        xi, pj = int(r["xbox_index"]), int(r["pc_index"])
        cx, cp = gx(xi), gp(pj)
        new, patched = patch_container(cx, cp)
        ok = verify(new, cx, cp)
        (out / f"unknow_{pj:05d}.bin").write_bytes(new)
        print(f"PC#{pj:<4} <- X#{xi:<4} texturas con ID corregido: {patched:<3} verificado: {'si' if ok else 'NO'}")


if __name__ == "__main__":
    main(*sys.argv[1:6])
