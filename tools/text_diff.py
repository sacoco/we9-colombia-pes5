"""Diff the strings inside Konami-compressed entries of two aligned AFS archives."""
import csv
import difflib
import re
import struct
import sys
import zlib


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


def unpack(d):
    if d[:4] == b"\x00\x06\x01\x00":
        try:
            return zlib.decompress(d[32:])
        except zlib.error:
            return None
    return None


def strings(raw):
    out = []
    for chunk in raw.split(b"\x00"):
        try:
            s = chunk.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if len(s) >= 2 and re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñü]{2}", s) and s.isprintable():
            out.append(s)
    return out


def main(xbox_afs, pc_afs, align_csv, out_txt):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    gx, gp = reader(xbox_afs), reader(pc_afs)
    pairs = [r for r in csv.DictReader(open(align_csv, encoding="utf-8")) if r["xbox_index"] and r["pc_index"]]
    kinds = {}
    with open(out_txt, "w", encoding="utf-8") as out:
        for r in pairs:
            xi, pj = int(r["xbox_index"]), int(r["pc_index"])
            rx, rp = unpack(gx(xi)), unpack(gp(pj))
            if rx is None or rp is None:
                kinds["sin_comprimir"] = kinds.get("sin_comprimir", 0) + 1
                continue
            sx, sp = strings(rx), strings(rp)
            if len(sx) < 3 and len(sp) < 3:
                kinds["binario/textura"] = kinds.get("binario/textura", 0) + 1
                continue
            kinds["texto"] = kinds.get("texto", 0) + 1
            diff = [l for l in difflib.unified_diff(sp, sx, "PC", "XBOX", n=0, lineterm="") if not l.startswith(("---", "+++", "@@"))]
            if diff:
                out.write(f"\n===== Xbox #{xi}  <->  PC #{pj}  ({len(diff)} lineas distintas)\n")
                out.write("\n".join(diff) + "\n")
    print("tipos de entradas reemplazadas:", kinds)
    print("diff:", out_txt)


if __name__ == "__main__":
    main(*sys.argv[1:5])
