"""Copy club names from the Xbox XBE team table into a PES5 PC option file.

Matching is by 3-letter abbreviation (the Xbox patch kept the original abbreviations).
Field offsets follow PeterC10/PES5Editor (TeamPanel.java): name at +0 (49 bytes),
abbreviation at +73, 'edited' flag at +110.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pes5_of import CLUB_COUNT, CLUB_SIZE, CLUBS_OFF, decrypt, encrypt  # noqa: E402

NAME_LEN = 49
ABBR_OFF = 73
FLAG_OFF = 110


def xbe_pairs(xbe, start_marker=b"Udinese\x00", count=18):
    pos = xbe.index(start_marker)
    pairs, i = [], pos
    while len(pairs) < count + 1:
        m = re.compile(rb"([^\x00]+)\x00+").match(xbe, i)
        name = m.group(1).decode("latin-1")
        i = m.end()
        while i % 4:
            i += 1
        abbr = xbe[i:i + 4].split(b"\x00")[0].decode("latin-1")
        i += 4
        pairs.append((name, abbr))
    return pairs[1:]


def main(xbe_path, of_in, of_out):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pairs = xbe_pairs(Path(xbe_path).read_bytes())
    plain = decrypt(Path(of_in).read_bytes())
    by_abbr = {}
    for idx in range(CLUB_COUNT):
        base = CLUBS_OFF + idx * CLUB_SIZE
        abbr = plain[base + ABBR_OFF:base + ABBR_OFF + 3].split(b"\x00")[0].decode("latin-1")
        by_abbr.setdefault(abbr, []).append(idx)

    for name, abbr in pairs:
        targets = by_abbr.get(abbr, [])
        if len(targets) != 1:
            print(f"  SALTEADO {abbr} -> {name}: coincidencias {targets}")
            continue
        idx = targets[0]
        base = CLUBS_OFF + idx * CLUB_SIZE
        old = plain[base:base + NAME_LEN].split(b"\x00")[0].decode("latin-1")
        encoded = name.encode("utf-8")[:NAME_LEN - 1]
        plain[base:base + NAME_LEN] = encoded + b"\x00" * (NAME_LEN - len(encoded))
        plain[base + FLAG_OFF] = 1
        print(f"  club {idx:3d} [{abbr}] {old:<20} -> {name}")

    Path(of_out).write_bytes(encrypt(plain))
    print(f"guardado: {of_out}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
