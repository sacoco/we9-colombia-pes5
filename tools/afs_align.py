"""Align two AFS archives entry-by-entry (like diff) to map Xbox indices to PC indices.

Pass 1 aligns by content hash. Inside each non-equal block, pass 2 aligns by exact
entry size; leftover sub-blocks of equal length are paired by position only when the
entries look like the same kind of file (same 4-byte header, size within 2x).
Pairs that fail that check are emitted unpaired as `ambiguous`.
"""
import csv
import difflib
import hashlib
import struct
import sys


def entry_info(path):
    out = []
    with open(path, "rb") as f:
        f.seek(4)
        count = struct.unpack("<I", f.read(4))[0]
        table = f.read(count * 8)
        for i in range(count):
            off, size = struct.unpack_from("<II", table, i * 8)
            f.seek(off)
            data = f.read(size)
            out.append((hashlib.sha1(data).hexdigest(), size, data[:4]))
    return out


def same_kind(a, b):
    return a[2] == b[2] and a[1] and b[1] and 0.5 <= a[1] / b[1] <= 2.0


def refine(x, p, i1, i2, j1, j2):
    """Yield (match, xi, pj) for a non-equal block."""
    sm = difflib.SequenceMatcher(None, [e[1] for e in x[i1:i2]], [e[1] for e in p[j1:j2]], autojunk=False)
    for tag, a1, a2, b1, b2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(a2 - a1):
                yield "same_size", i1 + a1 + k, j1 + b1 + k
            continue
        if tag == "replace" and a2 - a1 == b2 - b1:
            for k in range(a2 - a1):
                xi, pj = i1 + a1 + k, j1 + b1 + k
                if same_kind(x[xi], p[pj]):
                    yield "positional", xi, pj
                else:
                    yield "ambiguous", xi, None
                    yield "ambiguous", None, pj
            continue
        for k in range(a2 - a1):
            yield ("xbox_only" if tag == "delete" else "ambiguous"), i1 + a1 + k, None
        for k in range(b2 - b1):
            yield ("pc_only" if tag == "insert" else "ambiguous"), None, j1 + b1 + k


def main(xbox_afs, pc_afs, out_csv):
    x = entry_info(xbox_afs)
    p = entry_info(pc_afs)
    sm = difflib.SequenceMatcher(None, [e[0] for e in x], [e[0] for e in p], autojunk=False)

    rows, totals = [], {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            totals["identical"] = totals.get("identical", 0) + (i2 - i1)
            continue
        for match, xi, pj in refine(x, p, i1, i2, j1, j2):
            totals[match] = totals.get(match, 0) + 1
            rows.append({
                "block": match,
                "xbox_index": "" if xi is None else xi,
                "pc_index": "" if pj is None else pj,
                "xbox_size": "" if xi is None else x[xi][1],
                "pc_size": "" if pj is None else p[pj][1],
                "xbox_magic": "" if xi is None else x[xi][2].hex(),
                "pc_magic": "" if pj is None else p[pj][2].hex(),
            })

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["block", "xbox_index", "pc_index", "xbox_size", "pc_size", "xbox_magic", "pc_magic"])
        w.writeheader()
        w.writerows(rows)
    print(f"  {totals}")
    print(f"  CSV: {out_csv}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
