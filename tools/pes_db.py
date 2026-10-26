"""Read the PES5/WE9 default database containers stored in 0_text.afs.

Layout (from PES5.exe sub_8EDBE0 / sub_8EF260): 32-byte header, container at 0x20 with
count, 8, then count offsets relative to 0x20; each section is a '00 00 01 00' zlib block.
File IDs 0x10011..0x10018 map to database sections:
  0x10016 -> 0..6, 0x10018 -> 7..9, 0x10017 -> 10..12, 0x10013 -> 13..17,
  0x10012 -> 18, 0x10011 -> 19..24
"""
import struct
import zlib

BASE = 0x20


def sections(entry):
    count = struct.unpack_from("<I", entry, BASE)[0]
    offs = struct.unpack_from(f"<{count}I", entry, BASE + 8)
    out = []
    for off in offs:
        blk = entry[BASE + off:]
        csize, usize = struct.unpack_from("<II", blk, 4)
        raw = zlib.decompress(blk[32:32 + csize]) if blk[2] == 1 else blk[32:32 + usize]
        out.append(raw)
    return out


def afs_entry(path, i):
    with open(path, "rb") as f:
        f.seek(8 + i * 8)
        off, size = struct.unpack("<II", f.read(8))
        f.seek(off)
        return f.read(size)
