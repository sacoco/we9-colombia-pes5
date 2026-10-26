"""Search game files for an option-file-style encrypted copy of a known player name."""
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pes5_of import OF_KEY  # noqa: E402

MASK = 0xFFFFFFFF
LAST = OF_KEY[-1]


def patterns(name, words=3):
    plain = name.encode("utf-16-le")[:words * 4]
    ws = struct.unpack(f"<{words}I", plain)
    for k in range(len(OF_KEY)):
        enc = [(OF_KEY[(k + j) % len(OF_KEY)] + (((w ^ LAST) - LAST) & MASK)) & MASK for j, w in enumerate(ws)]
        yield k, struct.pack(f"<{words}I", *enc)
    yield "plano", plain


def scan(label, data, pats):
    for k, pat in pats:
        pos = data.find(pat)
        if pos != -1:
            print(f"  ENCONTRADO en {label} @0x{pos:x} (fase de clave {k})")


def afs_entries(path):
    data = Path(path).read_bytes()
    count = struct.unpack_from("<I", data, 4)[0]
    for i in range(count):
        o, s = struct.unpack_from("<II", data, 8 + i * 8)
        d = data[o:o + s]
        yield i, d
        if d[:4] in (b"\x00\x06\x01\x00", b"\x00\x03\x01\x00"):
            try:
                yield f"{i}z", zlib.decompress(d[32:])
            except zlib.error:
                pass


if __name__ == "__main__":
    name = sys.argv[1]
    pats = list(patterns(name))
    for path in sys.argv[2:]:
        print(path)
        if path.lower().endswith(".afs"):
            for i, d in afs_entries(path):
                scan(f"#{i}", d, pats)
        else:
            scan(Path(path).name, Path(path).read_bytes(), pats)
