"""Decode Konami PES textures (container 00 02 00 00, zlib 00 03 01 00 / 00 06 01 00, image 94 72 85 29) to PNG."""
import struct
import zlib

from PIL import Image

TEX_MAGIC = b"\x94\x72\x85\x29"
ZLIB_HEADERS = (b"\x00\x03\x01\x00", b"\x00\x06\x01\x00")


def unswizzle_clut(pal):
    out = list(pal)
    for block in range(0, 256, 32):
        out[block + 8:block + 16] = pal[block + 16:block + 24]
        out[block + 16:block + 24] = pal[block + 8:block + 16]
    return out


def decode_texture(raw):
    if raw[:4] != TEX_MAGIC or len(raw) < 0x20:
        return None
    pix_off, pal_off, w, h = struct.unpack_from("<HHHH", raw, 0x10)
    ncolors = (pix_off - pal_off) // 4
    if not w or not h or ncolors not in (16, 256):
        return None
    pal = [tuple(raw[pal_off + i * 4:pal_off + i * 4 + 4]) for i in range(ncolors)]
    if ncolors == 256:
        pal = unswizzle_clut(pal)
    rgba = [(r, g, b, min(255, a * 2)) for r, g, b, a in pal]

    px = raw[pix_off:]
    if ncolors == 16:
        idx = bytearray()
        for byte in px[:w * h // 2]:
            idx.append(byte & 0x0F)
            idx.append(byte >> 4)
    else:
        idx = px[:w * h]
    if len(idx) < w * h:
        return None
    img = Image.new("RGBA", (w, h))
    img.putdata([rgba[i] for i in idx[:w * h]])
    return img


def _inflate(data, pos):
    csize = struct.unpack_from("<I", data, pos + 4)[0]
    try:
        return zlib.decompress(data[pos + 32:pos + 32 + csize]), pos + 32 + csize
    except zlib.error:
        return None, pos + 4


def textures_in(entry):
    """Return the list of raw textures found inside an AFS entry."""
    if entry[:4] in ZLIB_HEADERS:
        raw, _ = _inflate(entry, 0)
        if raw is None:
            return []
        entry = raw
    if entry[:4] == TEX_MAGIC:
        return [entry]

    found = []
    pos = 0
    while True:
        cands = [p for p in [entry.find(h, pos) for h in ZLIB_HEADERS + (TEX_MAGIC,)] if p != -1]
        if not cands:
            return found
        nxt = min(cands)
        if entry[nxt:nxt + 4] == TEX_MAGIC:
            size = struct.unpack_from("<I", entry, nxt + 8)[0]
            found.append(entry[nxt:nxt + size])
            pos = nxt + max(size, 4)
        else:
            raw, pos = _inflate(entry, nxt)
            if raw is not None and raw[:4] == TEX_MAGIC:
                found.append(raw)
