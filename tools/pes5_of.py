"""PES5 PC option file (KONAMI-WIN32PES5OPT) decrypt/encrypt and field access.

Crypto and layout adapted from moth1995/PES5_WE9_LE_OF_Team_Editor (MIT, see vendor/moth1995/LICENSE).
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "vendor" / "moth1995"))
from option_file_data import OF_BLOCK, OF_BLOCK_SIZE, OF_BYTE_LENGTH, OF_KEY, OF_KEY_PC  # noqa: E402

PLAYERS_OFF = 36872
PLAYER_SIZE = 124
EDITED_OFF = 14044
FIRST_EDITED_ID = 32768
CLUBS_OFF = 803608
CLUB_SIZE = 140
CLUB_COUNT = 138
MASK = 0xFFFFFFFF


def _xor_pc(data):
    for i in range(OF_BYTE_LENGTH):
        data[i] ^= OF_KEY_PC[i & 0xFF]


def _blocks():
    for start, size in zip(OF_BLOCK[1:], OF_BLOCK_SIZE[1:]):
        yield start, size


def decrypt(raw):
    data = bytearray(raw)
    _xor_pc(data)
    last = OF_KEY[-1]
    for start, size in _blocks():
        for k, a in enumerate(range(start, start + size, 4)):
            c = struct.unpack_from("<I", data, a)[0]
            p = (((c - OF_KEY[k % len(OF_KEY)]) & MASK) + last & MASK) ^ last
            struct.pack_into("<I", data, a, p)
    return data


def encrypt(plain):
    data = bytearray(plain)
    last = OF_KEY[-1]
    for start, size in _blocks():
        for k, a in enumerate(range(start, start + size, 4)):
            p = struct.unpack_from("<I", data, a)[0]
            c = (OF_KEY[k % len(OF_KEY)] + (((p ^ last) - last) & MASK)) & MASK
            struct.pack_into("<I", data, a, c)
    for start, size in zip(OF_BLOCK, OF_BLOCK_SIZE):
        checksum = sum(struct.unpack_from(f"<{size // 4}I", data, start)) & MASK
        struct.pack_into("<I", data, start - 8, checksum)
    _xor_pc(data)
    return data


def player_offset(pid):
    if pid >= FIRST_EDITED_ID:
        return EDITED_OFF + (pid - FIRST_EDITED_ID) * PLAYER_SIZE
    return PLAYERS_OFF + pid * PLAYER_SIZE


def player_name(data, pid):
    o = player_offset(pid)
    return data[o:o + 32].decode("utf-16-le", "replace").split("\0")[0]


def player_shirt(data, pid):
    o = player_offset(pid) + 32
    return data[o:o + 16].split(b"\0")[0].decode("latin-1")


def club_name(data, idx):
    o = CLUBS_OFF + idx * CLUB_SIZE
    return data[o:o + 49].split(b"\0")[0].decode("latin-1")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    plain = decrypt(Path(sys.argv[1]).read_bytes())
    again = encrypt(plain)
    orig = Path(sys.argv[1]).read_bytes()
    print("ida y vuelta identica:", bytes(again) == orig)
    for pid in (1, 2, 3, 100, 1000):
        print(f"jugador {pid}: {player_name(plain, pid)!r} / camiseta {player_shirt(plain, pid)!r}")
    print("clubes:", [club_name(plain, i) for i in range(0, CLUB_COUNT, 10)])
