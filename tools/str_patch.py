"""Replace exact strings inside PES5 text tables (s_text.afs .str entries) and rebuild them.

Entry: 32-byte header '00 06 01 00' csize usize, zlib payload.
Payload: container (u32 count, u32 8, count offsets), 16-aligned sub-blocks with a
32-byte '00 04 00 00' header (size twice). Sub-block data:
  u32 n, u32 unknown, n x {u32 id, u16 bytes incl NUL, u16 chars, u32 offset}, UTF-8 strings.
"""
import struct
import sys
import zlib
from pathlib import Path


def parse_table(d):
    n, unk = struct.unpack_from("<II", d, 0)
    entries = [struct.unpack_from("<IHHI", d, 8 + 12 * k) for k in range(n)]
    return unk, entries


def rebuild_table(d, repl):
    unk, entries = parse_table(d)
    start = 8 + 12 * len(entries)
    texts, out_entries, changed = bytearray(), [], 0
    placed = {}
    for sid, blen, clen, off in entries:
        if off not in placed:
            s = d[off:off + blen - 1].decode("utf-8")
            if s in repl:
                s = repl[s]
                changed += 1
            raw = s.encode("utf-8")
            placed[off] = (start + len(texts), len(raw) + 1, len(s))
            texts += raw + b"\x00"
        noff, nblen, nclen = placed[off]
        out_entries.append((sid, nblen, nclen, noff))
    head = struct.pack("<II", len(entries), unk) + b"".join(struct.pack("<IHHI", *e) for e in out_entries)
    return head + bytes(texts), changed


def patch_entry(entry, repl):
    csize = struct.unpack_from("<I", entry, 4)[0]
    raw = zlib.decompress(entry[32:32 + csize])
    count = struct.unpack_from("<I", raw, 0)[0]
    offs = struct.unpack_from(f"<{count}I", raw, 8)

    out = bytearray(raw[:offs[0]])
    total = 0
    for k, off in enumerate(offs):
        hdr = bytearray(raw[off:off + 32])
        size = struct.unpack_from("<I", hdr, 4)[0]
        data, changed = rebuild_table(raw[off + 32:off + 32 + size], repl)
        total += changed
        struct.pack_into("<II", hdr, 4, len(data), len(data))
        while len(out) % 16:
            out.append(0)
        struct.pack_into("<I", out, 8 + 4 * k, len(out))
        out += hdr + data
    while len(out) % 16:
        out.append(0)
    comp = zlib.compress(bytes(out), 9)
    new = bytearray(entry[:32])
    struct.pack_into("<II", new, 4, len(comp), len(out))
    return bytes(new) + comp, total


def strings_of(entry):
    csize = struct.unpack_from("<I", entry, 4)[0]
    raw = zlib.decompress(entry[32:32 + csize])
    count = struct.unpack_from("<I", raw, 0)[0]
    out = []
    for off in struct.unpack_from(f"<{count}I", raw, 8):
        size = struct.unpack_from("<I", raw, off + 4)[0]
        d = raw[off + 32:off + 32 + size]
        _, entries = parse_table(d)
        out.append([d[o:o + b - 1].decode("utf-8") for _, b, _, o in entries])
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    afs, out_dir = sys.argv[1], Path(sys.argv[2])
    indices = [int(i) for i in sys.argv[3].split(",")]
    repl = dict(pair.split("=", 1) for pair in sys.argv[4:])
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(afs, "rb") as f:
        f.seek(4)
        n = struct.unpack("<I", f.read(4))[0]
        table = f.read(n * 8)
        for i in indices:
            o, s = struct.unpack_from("<II", table, i * 8)
            f.seek(o)
            entry = f.read(s)
            new, changed = patch_entry(entry, repl)
            before, after = strings_of(entry), strings_of(new)
            diffs = [(a, b) for ta, tb in zip(before, after) for a, b in zip(ta, tb) if a != b]
            assert all(repl.get(a) == b for a, b in diffs), diffs
            assert sum(map(len, before)) == sum(map(len, after))
            (out_dir / f"unknow_{i:05d}.bin").write_bytes(new)
            print(f"#{i}: {changed} textos reemplazados, verificado {len(diffs)} cambios esperados: {sorted(set(diffs))}")
