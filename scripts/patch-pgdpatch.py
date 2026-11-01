#!/usr/bin/env python3
"""Keep QEMU's prepopulated initial page table in the Sony A7M3 kernel.

The camera kernel's head.S clears swapper_pg_dir before using it; QEMU
prepopulates one L1 entry so the PAGE_OFFSET jump works before setup_arch
reads the ATAGS.  The first instruction inside the pgd-zeroing loop at
0x60108068 is redirected to skip the clear.

Original word: 0xe4803004  (str r3, [r0], #4)
Patch:          0xea000004  (b 0x60108080)

Source kernel: the raw ARM Image `vmlinux.bin` from the camera's system
partition (nflasha3.bin, FAT file VMLINUX.BIN).

Usage: patch-pgdpatch.py [src] [dst]
"""
import hashlib
import os
import shutil
import struct
import sys

D = os.path.expanduser("~/firmware/a7m3")
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(D, "vmlinux.bin")
DST = sys.argv[2] if len(sys.argv) > 2 else os.path.join(D, "vmlinux-pgdpatch.bin")

BASE = 0x60108000
VA = 0x60108068
ORIG = 0xE4803004
NEW = 0xEA000004


def main():
    if not os.path.isfile(SRC):
        sys.exit("no such file: %s" % SRC)
    if os.path.getsize(SRC) < VA - BASE + 4:
        sys.exit("%s is too small to be the A7M3 kernel" % SRC)

    shutil.copyfile(SRC, DST)
    data = bytearray(open(DST, "rb").read())
    off = VA - BASE
    old = struct.unpack_from("<I", data, off)[0]
    print("kernel %s (%d bytes)" % (SRC, len(data)))
    print("word @0x%x (VA 0x%08x): 0x%08x" % (off, VA, old))
    if old == NEW:
        print("already patched")
    elif old != ORIG:
        os.unlink(DST)
        sys.exit("unexpected word; refusing to patch (different firmware?)")
    else:
        struct.pack_into("<I", data, off, NEW)
        open(DST, "wb").write(data)
        check = struct.unpack_from("<I", open(DST, "rb").read(), off)[0]
        if check != NEW:
            sys.exit("read-back mismatch: 0x%08x" % check)
        print("patched: 0x%08x -> 0x%08x" % (old, check))

    print("wrote %s (%d bytes)" % (DST, os.path.getsize(DST)))
    print("sha256 %s" % hashlib.sha256(open(DST, "rb").read()).hexdigest())


if __name__ == "__main__":
    main()
