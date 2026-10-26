import csv
import hashlib
import struct
import sys
from collections import defaultdict
from pathlib import Path


def read_afs(path):
    with open(path, "rb") as f:
        head = f.read(8)
        if head[:3] != b"AFS":
            raise ValueError(f"{path}: not an AFS file")
        count = struct.unpack_from("<I", head, 4)[0]
        table = f.read(count * 8 + 8)
        entries = [struct.unpack_from("<II", table, i * 8) for i in range(count)]
        name_off, name_size = struct.unpack_from("<II", table, count * 8)
        if name_off == 0 and entries:
            first = min(o for o, s in entries if s)
            f.seek(first - 8)
            name_off, name_size = struct.unpack("<II", f.read(8))

        names = [""] * count
        if name_off and name_size >= count * 48:
            f.seek(name_off)
            raw = f.read(count * 48)
            for i in range(count):
                n = raw[i * 48:i * 48 + 32].split(b"\x00")[0]
                names[i] = n.decode("ascii", errors="replace")

        result = []
        for i, (off, size) in enumerate(entries):
            f.seek(off)
            data = f.read(size)
            result.append({
                "index": i,
                "offset": off,
                "size": size,
                "name": names[i],
                "kind": classify(data),
                "magic": data[:8].hex(),
                "sha1": hashlib.sha1(data).hexdigest(),
            })
        return result


def classify(d):
    if not d:
        return "empty"
    if d[:2] == b"\x80\x00":
        return "ADX"
    if d[:4] == b"RIFF":
        fmt = d.find(b"fmt ")
        if fmt != -1 and len(d) >= fmt + 10:
            tag = struct.unpack_from("<H", d, fmt + 8)[0]
            return {0x0001: "WAV-PCM", 0x0069: "WAV-XboxADPCM", 0x0161: "WAV-WMA",
                    0x0011: "WAV-IMAADPCM", 0x0002: "WAV-MSADPCM"}.get(tag, f"WAV-0x{tag:04x}")
        return "RIFF"
    if d[:4] == b"AFS\x00":
        return "AFS"
    if d[:4] in (b"WBND", b"DNBW"):
        return "XWB"
    if d[:5] == b"WESYS":
        return "WESYS"
    if d[:2] in (b"\x78\x9c", b"\x78\xda", b"\x78\x01"):
        return "zlib"
    if d[:4] == b"\x00\x01\x01\x00":
        return "PES-compressed?"
    return "other"


def compare(xbox_path, pc_path, out_dir):
    name = Path(xbox_path).name
    x = read_afs(xbox_path)
    p = read_afs(pc_path)

    pc_by_hash = defaultdict(list)
    for e in p:
        pc_by_hash[e["sha1"]].append(e["index"])

    rows = []
    stats = defaultdict(int)
    for e in x:
        i = e["index"]
        pe = p[i] if i < len(p) else None
        if pe and pe["sha1"] == e["sha1"]:
            status = "identical"
        elif e["sha1"] in pc_by_hash:
            status = "moved"
        elif pe is None:
            status = "xbox_only"
        else:
            status = "different"
        stats[status] += 1
        rows.append({
            "index": i,
            "status": status,
            "xbox_name": e["name"], "xbox_size": e["size"], "xbox_kind": e["kind"], "xbox_magic": e["magic"],
            "pc_name": pe["name"] if pe else "", "pc_size": pe["size"] if pe else "",
            "pc_kind": pe["kind"] if pe else "", "pc_magic": pe["magic"] if pe else "",
            "same_content_at_pc_index": " ".join(map(str, pc_by_hash.get(e["sha1"], []))),
        })

    out = Path(out_dir) / f"{name}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    def kinds(entries):
        k = defaultdict(int)
        for e in entries:
            k[e["kind"]] += 1
        return dict(k)

    print(f"=== {name} ===")
    print(f"  entradas: Xbox={len(x)}  PC={len(p)}")
    print(f"  nombres internos: Xbox={'si' if any(e['name'] for e in x) else 'no'}  PC={'si' if any(e['name'] for e in p) else 'no'}")
    print(f"  formatos Xbox: {kinds(x)}")
    print(f"  formatos PC:   {kinds(p)}")
    print(f"  comparacion:   {dict(stats)}")
    print(f"  bytes Xbox={sum(e['size'] for e in x):,}  PC={sum(e['size'] for e in p):,}")
    print(f"  CSV: {out}")
    print()


if __name__ == "__main__":
    xbox_dir, pc_dir, out_dir = sys.argv[1:4]
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for fname in sys.argv[4:]:
        compare(Path(xbox_dir) / fname, Path(pc_dir) / fname, out_dir)
