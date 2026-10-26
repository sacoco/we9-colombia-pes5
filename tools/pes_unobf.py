"""Undo the PES5/WE9 header-keyed obfuscation of protected AFS entries and decompress them.

Reverse engineered from PES5.exe sub_84C4C0 (calls the kit decoder at 0x829360, the
C_UNIDECODE hook point in KitServer 5).
"""
import struct
import zlib

M = 0xFFFFFFFF


def is_protected(entry):
    return entry[:4] == b"\x00\x06\x01\x00" and any(entry[0x10:0x20])


def unobfuscate(entry):
    w = list(struct.unpack_from("<16I", entry, 0))
    w[8] ^= ((w[6] + w[7]) & M) & 0x230AB3FE
    w[10] ^= (w[4] + (w[5] & 0xFEA938F2)) & M
    w[11] ^= ((w[7] - w[5]) & M) & 0x8A10A67A
    w[15] ^= (w[4] - (w[6] & 0x37AA3BEF)) & M
    return struct.pack("<16I", *w) + entry[64:]


def checksum(entry):
    n = len(entry) // 4
    w = struct.unpack_from(f"<{n}I", entry, 0)
    i = ((w[1] + w[9]) & M) ^ 0x2332296E
    for v in range(1, (w[1] >> 2) - 1, 32):
        if v + 8 < n:
            i ^= w[v + 8]
    return i


def tamper_ok(entry):
    """The game's anti-tamper check. On mismatch PES5 sets a global flag that stops it from
    loading the second (low-detail) kit texture for every kit loaded afterwards."""
    return checksum(entry) == struct.unpack_from("<I", entry, 0x10)[0]


def reprotect(entry):
    """Rewrite a protected entry so its header carries a valid anti-tamper checksum."""
    plain = bytearray(unobfuscate(entry))
    struct.pack_into("<I", plain, 0x10, checksum(plain))
    return unobfuscate(bytes(plain))


def decode(entry):
    """Return the decompressed payload of a 00 06 01 00 entry (protected or not)."""
    if is_protected(entry):
        entry = unobfuscate(entry)
    csize = struct.unpack_from("<I", entry, 4)[0]
    return zlib.decompress(entry[32:32 + csize])
