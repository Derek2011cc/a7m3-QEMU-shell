#!/usr/bin/env python3
"""Minimal FAT12/FAT16 lister/extractor for the A7M3 vfat partitions.

Only what is needed to pull VMLINUX.BIN and INITRD.IMG out of nflasha3,
plus directory listing for inspection.  No LFN support: these partitions
use plain 8.3 names.

Usage:
  fat-extract.py IMAGE                 # list recursively
  fat-extract.py IMAGE PATH            # extract PATH to ./basename
  fat-extract.py IMAGE PATH -o OUT     # extract to OUT
"""
import argparse
import hashlib
import os
import struct
import sys


def u16(buf, off):
    return struct.unpack_from("<H", buf, off)[0]


def u32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


class Entry:
    def __init__(self, name, ext, attr, cluster, size):
        self.name = name
        self.ext = ext
        self.attr = attr
        self.cluster = cluster
        self.size = size
        self.path = ""

    @property
    def is_dir(self):
        return bool(self.attr & 0x10)

    @property
    def filename(self):
        return self.name + ("." + self.ext if self.ext else "")


class Fat:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.raw = f.read()
        bs = self.raw[:512]
        if len(bs) < 512 or bs[510:512] != b"\x55\xaa":
            sys.exit("%s: not a FAT boot sector" % path)

        self.bps = u16(bs, 11)
        self.spc = bs[13]
        self.resv = u16(bs, 14)
        self.nfats = bs[16]
        self.root_entries = u16(bs, 17)
        self.tot16 = u16(bs, 19)
        self.fat_secs = u16(bs, 22)
        tot32 = u32(bs, 32)
        total = self.tot16 or tot32

        if self.bps not in (512, 1024, 2048, 4096) or self.spc == 0:
            sys.exit("%s: unsupported BPB (bps=%d spc=%d)"
                     % (path, self.bps, self.spc))
        if total == 0 or self.fat_secs == 0:
            sys.exit("%s: unsupported FAT (total=%d fat_secs=%d)"
                     % (path, total, self.fat_secs))

        self.root_secs = (self.root_entries * 32 + self.bps - 1) // self.bps
        self.fat_start = self.resv * self.bps
        self.root_start = (self.resv + self.nfats * self.fat_secs) * self.bps
        self.data_start = self.root_start + self.root_secs * self.bps

        data_secs = total - (self.resv + self.nfats * self.fat_secs
                             + self.root_secs)
        if data_secs <= 0:
            sys.exit("%s: empty data area" % path)
        clusters = data_secs // self.spc
        if clusters < 4085:
            self.bits = 12
        elif clusters < 65525:
            self.bits = 16
        else:
            sys.exit("%s: FAT32 is not supported" % path)

        fat_end = self.fat_start + self.fat_secs * self.bps
        self.fat = self.raw[self.fat_start:fat_end]
        self.cluster_size = self.spc * self.bps
        if self.data_start >= len(self.raw):
            sys.exit("%s: truncated image (data starts at 0x%x, size 0x%x)"
                     % (path, self.data_start, len(self.raw)))

    def next_cluster(self, cl):
        if self.bits == 16:
            if cl * 2 + 2 > len(self.fat):
                return 0xFFF8
            return u16(self.fat, cl * 2)
        off = cl + cl // 2
        if off + 2 > len(self.fat):
            return 0xFF8
        v = u16(self.fat, off)
        return (v >> 4) if (cl & 1) else (v & 0xFFF)

    def chain(self, cl):
        out = []
        seen = set()
        while 2 <= cl < (0xFF8 if self.bits == 12 else 0xFFF8):
            if cl in seen:
                break
            seen.add(cl)
            out.append(cl)
            cl = self.next_cluster(cl)
        return out

    def read_chain(self, cl, size):
        data = bytearray()
        for c in self.chain(cl):
            off = self.data_start + (c - 2) * self.cluster_size
            data += self.raw[off:off + self.cluster_size]
            if size and len(data) >= size:
                break
        return bytes(data[:size] if size else data)

    def root_blob(self):
        return self.raw[self.root_start:self.root_start
                         + self.root_secs * self.bps]

    def dir_blob(self, entry):
        return self.read_chain(entry.cluster, 0)

    @staticmethod
    def parse_dir(blob):
        entries = []
        for off in range(0, len(blob) - 31, 32):
            e = blob[off:off + 32]
            if e[0] == 0x00:
                break
            if e[0] == 0xE5:
                continue
            attr = e[11]
            if attr == 0x0F or (attr & 0x08):
                continue
            name = e[:8].decode("latin-1").rstrip(" ")
            ext = e[8:11].decode("latin-1").rstrip(" ")
            if e[0] == 0x05:
                name = "\xe5" + name[1:]
            if name + ("." + ext if ext else "") in (".", ".."):
                continue
            entries.append(Entry(name, ext, attr, u16(e, 26), u32(e, 28)))
        return entries

    def walk(self, max_depth=8):
        seen_dirs = set()

        def rec(blob, prefix, depth):
            for ent in self.parse_dir(blob):
                ent.path = prefix + "/" + ent.filename
                yield ent
                if ent.is_dir and ent.filename not in (".", "..") \
                        and depth < max_depth:
                    if ent.cluster in seen_dirs:
                        continue
                    seen_dirs.add(ent.cluster)
                    yield from rec(self.dir_blob(ent), ent.path, depth + 1)

        yield from rec(self.root_blob(), "", 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("image")
    ap.add_argument("path", nargs="?")
    ap.add_argument("-o", "--output")
    ap.add_argument("-l", "--list", action="store_true",
                    help="list entries (default when PATH is omitted)")
    ap.add_argument("--max-depth", type=int, default=8)
    args = ap.parse_args()

    fat = Fat(args.image)
    print("FAT%d: bps=%d spc=%d root_entries=%d data_start=0x%x"
          % (fat.bits, fat.bps, fat.spc, fat.root_entries, fat.data_start),
          file=sys.stderr)

    if args.list or not args.path:
        for e in fat.walk(args.max_depth):
            kind = "d" if e.is_dir else "-"
            print("%s %8d %6d %s" % (kind, e.size, e.cluster, e.path or "/"))
        return

    want = args.path.replace("\\", "/").lstrip("/").lower()
    matches = []
    for e in fat.walk(args.max_depth):
        p = e.path.lstrip("/").lower()
        if p == want or (("/" not in want) and e.filename.lower() == want):
            matches.append(e)
    if not matches:
        sys.exit("not found: %s" % args.path)
    if len(matches) > 1:
        sys.exit("ambiguous path %s: %s"
                 % (args.path, ", ".join(m.path for m in matches)))
    ent = matches[0]
    if ent.is_dir:
        sys.exit("%s is a directory" % ent.path)

    out = args.output or os.path.basename(ent.path)
    data = fat.read_chain(ent.cluster, ent.size)
    if len(data) != ent.size:
        sys.exit("short read: got %d of %d bytes" % (len(data), ent.size))
    with open(out, "wb") as f:
        f.write(data)
    print("wrote %s (%d bytes) sha256 %s"
          % (out, len(data), hashlib.sha256(data).hexdigest()))


if __name__ == "__main__":
    main()
