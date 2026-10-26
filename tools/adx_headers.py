import hashlib
import struct
import sys
from collections import Counter


def entries(path, indices):
    with open(path, "rb") as f:
        f.seek(4)
        count = struct.unpack("<I", f.read(4))[0]
        table = f.read(count * 8)
        for i in indices:
            off, size = struct.unpack_from("<II", table, i * 8)
            f.seek(off)
            yield i, f.read(size)


def adx_info(d):
    enc, block, bits, ch = d[4], d[5], d[6], d[7]
    rate, samples = struct.unpack_from(">II", d, 8)
    version = d[0x12]
    loop = ""
    if version == 3 and len(d) > 0x24:
        loop_flag = struct.unpack_from(">I", d, 0x18)[0]
        if loop_flag:
            ls, le = struct.unpack_from(">I", d, 0x1C)[0], struct.unpack_from(">I", d, 0x24)[0]
            loop = f"loop {ls/rate:.1f}s-{le/rate:.1f}s"
    elif version == 4 and len(d) > 0x34:
        loop_flag = struct.unpack_from(">I", d, 0x24)[0]
        if loop_flag:
            ls, le = struct.unpack_from(">I", d, 0x28)[0], struct.unpack_from(">I", d, 0x30)[0]
            loop = f"loop {ls/rate:.1f}s-{le/rate:.1f}s"
    return f"enc={enc} blk={block} bits={bits} ch={ch} {rate}Hz v{version} dur={samples/rate:6.1f}s {loop}"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    label, path = sys.argv[1], sys.argv[2]
    idx = range(int(sys.argv[3]), int(sys.argv[4]))
    hashes = Counter()
    for i, d in entries(path, idx):
        h = hashlib.sha1(d).hexdigest()[:10]
        hashes[h] += 1
        print(f"{label} [{i:3}] {h} {adx_info(d)}")
    dup = {h: n for h, n in hashes.items() if n > 1}
    print(f"{label}: {len(hashes)} unicas de {sum(hashes.values())}; duplicadas: {dup}")
