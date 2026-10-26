"""Extract mapped Xbox AFS entries into an AFS2FS override folder named by PC index.

The report CSV needs xbox_index/pc_index columns plus a status column (`status` or `kind`).
Rows from afs_compare.py (single `index` column) are treated as xbox_index == pc_index.
"""
import csv
import struct
import sys
from pathlib import Path


def main(source_afs, report_csv, out_root, statuses, ext):
    rows = []
    for r in csv.DictReader(open(report_csv, encoding="utf-8")):
        status = r.get("kind") or r.get("status")
        if status not in statuses:
            continue
        xi = r.get("xbox_index") or r.get("index")
        pj = r.get("pc_index") or r.get("index")
        if xi and pj:
            rows.append((int(xi), int(pj)))

    target = Path(out_root) / Path(source_afs).name
    target.mkdir(parents=True, exist_ok=True)
    with open(source_afs, "rb") as f:
        f.seek(4)
        count = struct.unpack("<I", f.read(4))[0]
        table = f.read(count * 8)
        total = 0
        for xi, pj in rows:
            off, size = struct.unpack_from("<II", table, xi * 8)
            f.seek(off)
            (target / f"unknow_{pj:05d}{ext}").write_bytes(f.read(size))
            total += size
    print(f"{len(rows)} archivos -> {target} ({total / 2**20:.0f} MB)")


if __name__ == "__main__":
    src, report, out = sys.argv[1:4]
    statuses = set(sys.argv[4].split(","))
    ext = sys.argv[5] if len(sys.argv) > 5 else ".bin"
    main(src, report, out, statuses, ext)
