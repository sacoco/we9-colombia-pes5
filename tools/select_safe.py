"""Select override pairs whose Xbox entry is the same kind of file the PC slot expects."""
import csv
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pes_tex import decode_texture, textures_in  # noqa: E402

COMPRESSED = (b"\x00\x06\x01\x00", b"\x00\x03\x01\x00")


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


def dims(entry):
    out = []
    for t in textures_in(entry):
        img = decode_texture(t)
        out.append(img.size if img else None)
    return out


def layout(entry):
    """Raw sizes of every compressed sub-block and texture inside an entry, in order."""
    sizes, pos = [], 0
    while True:
        cands = [p for p in [entry.find(h, pos) for h in COMPRESSED + (b"\x94\x72\x85\x29",)] if p != -1]
        if not cands:
            return sizes
        nxt = min(cands)
        if entry[nxt:nxt + 4] in COMPRESSED:
            csize, usize = struct.unpack_from("<II", entry, nxt + 4)
            sizes.append(("z", usize))
            pos = nxt + 32 + csize
        else:
            size = struct.unpack_from("<I", entry, nxt + 8)[0]
            sizes.append(("t", size))
            pos = nxt + max(size, 4)


def check(dx, dp, kind):
    if dx[:4] != dp[:4]:
        return False, "header distinto"
    if dx[:4] in COMPRESSED:
        rx, rp = struct.unpack_from("<I", dx, 8)[0], struct.unpack_from("<I", dp, 8)[0]
        if rx != rp:
            return False, f"descomprimido {rx} vs {rp}"
    elif dx[:4] == b"\x00\x02\x00\x00":
        lx, lp = layout(dx), layout(dp)
        if lx != lp:
            return False, f"estructura interna distinta ({len(lx)} vs {len(lp)} bloques)"
    else:
        ratio = len(dx) / len(dp) if dp else 0
        if not 0.8 <= ratio <= 1.25:
            return False, f"sin comprimir, proporcion {ratio:.2f}"
    if kind == "images_changed":
        a, b = dims(dx), dims(dp)
        if a != b:
            return False, "dimensiones distintas"
    return True, "misma estructura"


def main(xbox_afs, pc_afs, classified_csv, kinds, exclude_file, out_csv):
    gx, gp = reader(xbox_afs), reader(pc_afs)
    excluded = set()
    if exclude_file and Path(exclude_file).exists():
        excluded = {int(t) for t in Path(exclude_file).read_text().split()}
    kinds = set(kinds.split(","))
    out, stats = [], {}
    for r in csv.DictReader(open(classified_csv, encoding="utf-8")):
        if r["kind"] not in kinds or not r["xbox_index"] or not r["pc_index"]:
            continue
        xi, pj = int(r["xbox_index"]), int(r["pc_index"])
        if pj in excluded:
            ok, why = False, "excluido manualmente"
        else:
            ok, why = check(gx(xi), gp(pj), r["kind"])
        stats["ok" if ok else why.split(" ")[0]] = stats.get("ok" if ok else why.split(" ")[0], 0) + 1
        out.append({"xbox_index": xi, "pc_index": pj, "match": r["match"], "kind": "safe" if ok else "rejected", "reason": why})
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(stats)
    for r in out:
        if r["kind"] == "rejected" and r["reason"] != "excluido manualmente":
            print(f"  rechazado X#{r['xbox_index']} -> PC#{r['pc_index']}: {r['reason']}")


if __name__ == "__main__":
    main(*sys.argv[1:7])
