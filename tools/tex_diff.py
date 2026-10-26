"""Classify replaced AFS entries by comparing decompressed texture pixels/palettes."""
import csv
import hashlib
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pes_tex import TEX_MAGIC, textures_in  # noqa: E402


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


def image_key(raw):
    pix_off, pal_off, w, h = struct.unpack_from("<HHHH", raw, 0x10)
    return hashlib.sha1(struct.pack("<HH", w, h) + raw[pal_off:]).hexdigest()


def payload(entry):
    if entry[:4] in (b"\x00\x06\x01\x00", b"\x00\x03\x01\x00"):
        try:
            return zlib.decompress(entry[32:])
        except zlib.error:
            return entry
    return entry


def classify(ex, ep):
    tx, tp = textures_in(ex), textures_in(ep)
    if not tx and not tp:
        return ("same_data" if payload(ex) == payload(ep) else "data_diff"), 0, 0
    kx, kp = [image_key(t) for t in tx], [image_key(t) for t in tp]
    if kx == kp:
        return "same_images", len(kx), 0
    changed = sum(1 for a, b in zip(kx, kp) if a != b) + abs(len(kx) - len(kp))
    return "images_changed", len(kx), changed


def main(xbox_afs, pc_afs, align_csv, out_csv):
    gx, gp = reader(xbox_afs), reader(pc_afs)
    rows = list(csv.DictReader(open(align_csv, encoding="utf-8")))
    out, stats = [], {}
    for r in rows:
        xi = int(r["xbox_index"]) if r["xbox_index"] else None
        pj = int(r["pc_index"]) if r["pc_index"] else None
        if xi is None or pj is None:
            kind, n, changed = ("xbox_only" if pj is None else "pc_only"), 0, 0
        else:
            kind, n, changed = classify(gx(xi), gp(pj))
        stats[kind] = stats.get(kind, 0) + 1
        out.append({"xbox_index": xi, "pc_index": pj, "match": r["block"], "kind": kind,
                    "textures": n, "changed_textures": changed})
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(stats)
    print("CSV:", out_csv)


if __name__ == "__main__":
    main(*sys.argv[1:5])
