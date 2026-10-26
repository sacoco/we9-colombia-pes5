"""Decode the start of ADX entries from an AFS archive into WAV previews."""
import hashlib
import math
import struct
import sys
import wave
from pathlib import Path


def afs_entry(f, table, i):
    off, size = struct.unpack_from("<II", table, i * 8)
    f.seek(off)
    return f.read(size)


def decode_adx(d, seconds):
    data_off = struct.unpack_from(">H", d, 2)[0] + 4
    block, ch = d[5], d[7]
    rate, total = struct.unpack_from(">II", d, 8)
    highpass = struct.unpack_from(">H", d, 0x10)[0]

    a = math.sqrt(2) - math.cos(2 * math.pi * highpass / rate)
    b = math.sqrt(2) - 1
    c = (a - math.sqrt((a + b) * (a - b))) / b
    coef1 = int(c * 2 * 4096)
    coef2 = int(-(c * c) * 4096)

    per_block = (block - 2) * 2
    wanted = min(total, int(seconds * rate))
    hist = [[0, 0] for _ in range(ch)]
    out = [[] for _ in range(ch)]
    pos = data_off
    produced = 0
    while produced < wanted and pos + block * ch <= len(d):
        for c_i in range(ch):
            scale = struct.unpack_from(">h", d, pos)[0]
            h1, h2 = hist[c_i]
            buf = out[c_i]
            for byte in d[pos + 2:pos + block]:
                for nib in (byte >> 4, byte & 0xF):
                    if nib & 8:
                        nib -= 16
                    s = nib * scale + ((coef1 * h1 + coef2 * h2) >> 12)
                    s = 32767 if s > 32767 else (-32768 if s < -32768 else s)
                    buf.append(s)
                    h2, h1 = h1, s
            hist[c_i] = [h1, h2]
            pos += block
        produced += per_block

    n = min(len(x) for x in out)
    frames = bytearray()
    for i in range(n):
        for c_i in range(ch):
            frames += struct.pack("<h", out[c_i][i])
    return rate, ch, bytes(frames)


if __name__ == "__main__":
    afs_path, out_dir, first, last, seconds = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5])
    prefix = sys.argv[6] if len(sys.argv) > 6 else "track"
    out_dir.mkdir(parents=True, exist_ok=True)
    seen = {}
    with open(afs_path, "rb") as f:
        f.seek(4)
        count = struct.unpack("<I", f.read(4))[0]
        table = f.read(count * 8)
        for i in range(first, last):
            d = afs_entry(f, table, i)
            h = hashlib.sha1(d).hexdigest()
            if h in seen:
                seen[h].append(i)
                continue
            seen[h] = [i]
            rate, ch, frames = decode_adx(d, seconds)
            out = out_dir / f"{prefix}_{i:03d}.wav"
            with wave.open(str(out), "wb") as w:
                w.setnchannels(ch)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes(frames)
            print(f"{out.name}  ({len(frames) // (2 * ch) / rate:.0f}s)")
    print("\nslots que usa cada pista (indice de 0_sound.afs):")
    for h, idx in seen.items():
        print(f"  {prefix}_{idx[0]:03d}.wav -> {idx}")
