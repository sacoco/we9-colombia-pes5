"""Rebuild a PC AFS archive with replacement entries baked in (same entry count and order).

Override files are named like AFS2FS expects (anything_<index>.<ext>); the header region,
entry order and the (unused) trailing name-table pointer are kept from the original.
Entries stay 0x800-aligned.
"""
import re
import struct
import sys
from pathlib import Path

ALIGN = 0x800


def overrides_from(dirs):
    out = {}
    for d in dirs:
        for f in Path(d).iterdir():
            m = re.search(r"_(\d+)(\.[^.]*)?$", f.name)
            if f.is_file() and m:
                out[int(m.group(1))] = f
    return out


def rebuild(src, out, override_dirs):
    over = overrides_from(override_dirs)
    with open(src, "rb") as fi:
        head = bytearray(fi.read(8))
        n = struct.unpack_from("<I", head, 4)[0]
        toc = bytearray(fi.read(n * 8 + 8))
        entries = [struct.unpack_from("<II", toc, i * 8) for i in range(n)]
        first = entries[0][0]
        fi.seek(0)
        header = bytearray(fi.read(first))

        with open(out, "wb") as fo:
            fo.write(header)
            pos = first
            for i, (off, size) in enumerate(entries):
                if i in over:
                    data = over[i].read_bytes()
                else:
                    fi.seek(off)
                    data = fi.read(size)
                fo.write(data)
                struct.pack_into("<II", header, 8 + i * 8, pos, len(data))
                pos += len(data)
                pad = (-pos) % ALIGN
                fo.write(b"\x00" * pad)
                pos += pad
            fo.seek(0)
            fo.write(header)
    return n, len(over)


def verify(src, out, override_dirs):
    over = overrides_from(override_dirs)
    with open(src, "rb") as a, open(out, "rb") as b:
        na = struct.unpack("<I", (a.seek(4), a.read(4))[1])[0]
        nb = struct.unpack("<I", (b.seek(4), b.read(4))[1])[0]
        assert na == nb, (na, nb)
        ta = struct.unpack(f"<{na * 2}I", (a.seek(8), a.read(na * 8))[1])
        tb = struct.unpack(f"<{nb * 2}I", (b.seek(8), b.read(nb * 8))[1])
        for i in range(na):
            b.seek(tb[2 * i])
            got = b.read(tb[2 * i + 1])
            if i in over:
                want = over[i].read_bytes()
            else:
                a.seek(ta[2 * i])
                want = a.read(ta[2 * i + 1])
            if got != want:
                return f"entrada {i} distinta"
    return "ok"


if __name__ == "__main__":
    src, out, *dirs = sys.argv[1:]
    n, k = rebuild(src, out, dirs)
    print(f"{Path(out).name}: {n} entradas, {k} reemplazadas, verificacion: {verify(src, out, dirs)}")
