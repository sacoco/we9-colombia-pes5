"""Read-only access to an xemu qcow2 Xbox HDD image and its FATX partitions."""
import struct
import sys

PARTITIONS = {
    "X": (0x00080000, 0x2EE00000),
    "Y": (0x2EE80000, 0x2EE00000),
    "Z": (0x5DC80000, 0x2EE00000),
    "C": (0x8CA80000, 0x1F400000),
    "E": (0xABE80000, 0x131F00000),
}


class Qcow2:
    def __init__(self, path):
        self.f = open(path, "rb")
        hdr = self.f.read(72)
        if hdr[:4] != b"QFI\xfb":
            raise ValueError("no es qcow2")
        self.cluster_bits = struct.unpack_from(">I", hdr, 20)[0]
        self.cluster_size = 1 << self.cluster_bits
        self.size = struct.unpack_from(">Q", hdr, 24)[0]
        l1_size = struct.unpack_from(">I", hdr, 36)[0]
        l1_off = struct.unpack_from(">Q", hdr, 40)[0]
        self.f.seek(l1_off)
        self.l1 = struct.unpack(f">{l1_size}Q", self.f.read(l1_size * 8))
        self.l2_entries = self.cluster_size // 8
        self.l2_cache = {}

    def _cluster(self, vcluster):
        l1i, l2i = divmod(vcluster, self.l2_entries)
        l2_off = self.l1[l1i] & 0x00FFFFFFFFFFFE00
        if not l2_off:
            return None
        if l2_off not in self.l2_cache:
            self.f.seek(l2_off)
            self.l2_cache[l2_off] = struct.unpack(f">{self.l2_entries}Q", self.f.read(self.cluster_size))
        entry = self.l2_cache[l2_off][l2i]
        if entry & (1 << 62):
            raise NotImplementedError("cluster comprimido")
        return (entry & 0x00FFFFFFFFFFFE00) or None

    def read(self, off, n):
        out = bytearray()
        while n > 0:
            vc, within = divmod(off, self.cluster_size)
            chunk = min(n, self.cluster_size - within)
            host = self._cluster(vc)
            if host is None:
                out += b"\x00" * chunk
            else:
                self.f.seek(host + within)
                out += self.f.read(chunk)
            off += chunk
            n -= chunk
        return bytes(out)


class RawDisk:
    def __init__(self, path):
        self.f = open(path, "rb")

    def read(self, off, n):
        self.f.seek(off)
        return self.f.read(n)


def open_disk(path):
    with open(path, "rb") as f:
        magic = f.read(4)
    return Qcow2(path) if magic == b"QFI\xfb" else RawDisk(path)


class Fatx:
    def __init__(self, disk, start, size):
        self.disk, self.start = disk, start
        sb = disk.read(start, 4096)
        if sb[:4] != b"FATX":
            raise ValueError("particion sin FATX")
        self.spc = struct.unpack_from("<I", sb, 8)[0]
        self.root = struct.unpack_from("<I", sb, 12)[0]
        self.cluster_size = self.spc * 512
        clusters = size // self.cluster_size
        self.fat_width = 2 if clusters < 0xFFF0 else 4
        fat_bytes = (clusters + 1) * self.fat_width
        fat_bytes = (fat_bytes + 4095) & ~4095
        self.fat_off = start + 4096
        self.data_off = self.fat_off + fat_bytes
        self.fat = disk.read(self.fat_off, fat_bytes)

    def chain(self, first):
        end = 0xFFF0 if self.fat_width == 2 else 0xFFFFFFF0
        c, seen = first, 0
        while c and c < end and seen < 1_000_000:
            yield c
            c = struct.unpack_from("<H" if self.fat_width == 2 else "<I", self.fat, c * self.fat_width)[0]
            seen += 1

    def read_cluster(self, c):
        return self.disk.read(self.data_off + (c - 1) * self.cluster_size, self.cluster_size)

    def listdir(self, first):
        for c in self.chain(first):
            data = self.read_cluster(c)
            for o in range(0, len(data), 64):
                nl = data[o]
                if nl in (0x00, 0xFF):
                    return
                if nl == 0xE5 or nl > 42:
                    continue
                attr = data[o + 1]
                name = data[o + 2:o + 2 + nl].decode("latin-1")
                first_c, size = struct.unpack_from("<II", data, o + 44)
                yield name, attr, first_c, size

    def read_file(self, first, size):
        out = bytearray()
        for c in self.chain(first):
            out += self.read_cluster(c)
            if len(out) >= size:
                break
        return bytes(out[:size])

    def walk(self, first=None, path=""):
        for name, attr, c, size in self.listdir(first or self.root):
            full = f"{path}/{name}"
            if attr & 0x10:
                yield full, True, c, 0
                yield from self.walk(c, full)
            else:
                yield full, False, c, size


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    disk = open_disk(sys.argv[1])
    part = sys.argv[2] if len(sys.argv) > 2 else "E"
    prefix = sys.argv[3] if len(sys.argv) > 3 else "/UDATA"
    start, size = PARTITIONS[part]
    fs = Fatx(disk, start, size)
    for full, is_dir, c, size in fs.walk():
        if full.upper().startswith(prefix.upper()):
            print(f"{'<DIR>' if is_dir else size:>10}  {full}")
