#!/usr/bin/env python3
"""Disable grm_gles.ko's init_module inside the synthetic eMMC image.

The camera's Sugilite GPU driver calls BUG() in sugilite_clock_up_internal()
when the (unemulated) GPU clock never comes up.  init_module runs as pid 1's
syscall, so the BUG kills init.  Patching init_module to "mov r0,#0; bx lr"
makes module load succeed without touching the hardware.

The module lives in the nflasha15 ext2 image (mounted at /usr on the camera;
1024-byte blocks):
  /kmod/grm_gles.ko, inode 40880
  init_module = .init.text (file offset 0x1800) + symbol value 0x144
              = file offset 0x1944
  0x1944 -> block index 6, offset 324 -> physical block 173903, +324

The ext2 block constants are tied to the 4.03 service-mode dump.  The
partition LBA is read from the image's MBR unless --lba is given.  The script
always verifies the original ARM prologue before writing.

Usage: patch-grmgles.py [--lba N] <eMMC image>
"""
import argparse
import os
import struct
import sys

BOOT_OFF = 0x80000          # SD model user-area offset
EXT2_BLOCK = 173903         # block holding the patched bytes
EXT2_BLOCK_SIZE = 1024
OFF_IN_BLOCK = 324          # file offset 0x1944 - 6 * 1024

ORIG_PROLOGUE = bytes.fromhex("0dc0a0e1f0d82de9")   # mov r12,sp; push {r4-r7,...}
PATCH = bytes.fromhex("0000a0e31eff2fe1")           # mov r0,#0; bx lr


def u32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def find_logical_lba(path, partno):
    """Return the absolute start LBA of logical partition `partno` (5..25).

    EBR partition entries are relative: entry[0].start is relative to the
    current EBR, entry[1].start (next EBR) is relative to the extended
    partition base.
    """
    with open(path, "rb") as f:
        f.seek(BOOT_OFF)
        mbr = f.read(512)
        if len(mbr) != 512 or mbr[510:512] != b"\x55\xaa":
            sys.exit("no MBR signature at image offset 0x%x" % (BOOT_OFF + 510))

        ext_base = None
        for i in range(4):
            e = mbr[446 + i * 16:446 + (i + 1) * 16]
            if e[4] in (0x05, 0x0F, 0x85):
                ext_base = u32(e, 8)
        if not ext_base:
            sys.exit("no extended partition in MBR")

        idx = 5
        ebr_abs = ext_base
        seen = set()
        while ebr_abs and ebr_abs not in seen:
            seen.add(ebr_abs)
            f.seek(BOOT_OFF + ebr_abs * 512)
            ebr = f.read(512)
            if len(ebr) != 512 or ebr[510:512] != b"\x55\xaa":
                sys.exit("bad EBR at lba %d" % ebr_abs)
            e = ebr[446:462]
            rel_start = u32(e, 8)
            sectors = u32(e, 12)
            if rel_start == 0 and sectors == 0:
                break
            if idx == partno:
                return ebr_abs + rel_start
            idx += 1
            rel_next = u32(ebr[446 + 16:446 + 32], 8)
            ebr_abs = ext_base + rel_next if rel_next else 0
    sys.exit("logical partition %d not found" % partno)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--lba", type=lambda s: int(s, 0),
                    help="nflasha15 start LBA (default: read from MBR)")
    args = ap.parse_args()

    if not os.path.isfile(args.image):
        sys.exit("no such image: %s" % args.image)

    lba = args.lba if args.lba is not None else find_logical_lba(args.image, 15)
    off = BOOT_OFF + lba * 512 + EXT2_BLOCK * EXT2_BLOCK_SIZE + OFF_IN_BLOCK
    size = os.path.getsize(args.image)
    print("image %s (%d bytes), nflasha15 lba %d, patch offset 0x%x"
          % (args.image, size, lba, off))
    if off + 8 > size:
        sys.exit("patch offset beyond image size")

    with open(args.image, "rb") as f:
        f.seek(off)
        cur = f.read(8)
    print("current bytes:", cur.hex())

    if cur == PATCH:
        print("already patched; nothing to do")
        return
    if cur != ORIG_PROLOGUE:
        sys.exit("unexpected bytes; refusing to patch "
                 "(wrong firmware/layout, or pass the correct --lba)")

    with open(args.image, "r+b") as f:
        f.seek(off)
        f.write(PATCH)
    with open(args.image, "rb") as f:
        f.seek(off)
        new = f.read(8)
    if new != PATCH:
        sys.exit("read-back mismatch: %s" % new.hex())
    print("patched and verified:", new.hex())


if __name__ == "__main__":
    main()
