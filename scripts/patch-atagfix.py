#!/usr/bin/env python3
"""Restore the ATAGS pointer (r2) before the Sony A7M3 kernel calls __vet_atags.

The camera kernel's stext calls a Sony early-init routine at 0x6011efa0 which
clobbers r2 (it ends with `mvn r2, #0`).  Head then calls __vet_atags, which
sees an unaligned pointer, sets r2=0, and __atags_pointer stays 0.  As a
result meminfo.bank[0] is empty and prepare_page_table wipes the page table
that QEMU prepopulated.

Fix: redirect the __vet_atags call to a stub in zero padding at 0x60495f40
that loads 0x00010000 (the QEMU ATAGS address) into r2 and branches back to
the real vet routine.

Usage: patch-atagfix.py [src] [dst]
"""
import hashlib
import os
import shutil
import struct
import sys

D = os.path.expanduser("~/firmware/a7m3")
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(D, "vmlinux-pgdpatch.bin")
DST = sys.argv[2] if len(sys.argv) > 2 else os.path.join(D, "vmlinux-atagfix.bin")

BASE = 0x60108000
STUB = 0x60495F40
ATAGS = 0x00010000
VET = 0x60108118
HEAD_BL = 0x60108028


def va_off(va):
    return va - BASE


def encode_b(from_va, to_va):
    delta = to_va - (from_va + 8)
    if delta % 4:
        raise ValueError("unaligned branch")
    return 0xEA000000 | ((delta >> 2) & 0xFFFFFF)


def encode_bl(from_va, to_va):
    delta = to_va - (from_va + 8)
    if delta % 4:
        raise ValueError("unaligned branch")
    return 0xEB000000 | ((delta >> 2) & 0xFFFFFF)


def main():
    if not os.path.isfile(SRC):
        sys.exit("no such file: %s" % SRC)
    data = bytearray(open(SRC, "rb").read())

    stub_off = va_off(STUB)
    head_off = va_off(HEAD_BL)
    if stub_off + 16 > len(data) or head_off + 4 > len(data):
        sys.exit("%s is too small" % SRC)

    stub = [0xE59F2004, encode_b(STUB + 4, VET), 0, ATAGS]
    head_new = encode_bl(HEAD_BL, STUB)
    head_old = struct.unpack_from("<I", data, head_off)[0]

    print("kernel %s (%d bytes)" % (SRC, len(data)))
    print("__vet_atags call @0x%08x: 0x%08x" % (HEAD_BL, head_old))

    if head_old == head_new and \
            list(struct.unpack_from("<4I", data, stub_off)) == stub:
        print("already patched")
        shutil.copyfile(SRC, DST)
    else:
        if head_old != encode_bl(HEAD_BL, VET):
            sys.exit("unexpected call at 0x%08x; refusing to patch" % HEAD_BL)
        if data[stub_off:stub_off + 16] != b"\x00" * 16:
            sys.exit("stub area at 0x%08x is not zero; refusing to patch" % STUB)
        struct.pack_into("<4I", data, stub_off, *stub)
        struct.pack_into("<I", data, head_off, head_new)
        open(DST, "wb").write(data)
        check = struct.unpack_from("<4I", open(DST, "rb").read(), stub_off)
        if list(check) != stub:
            sys.exit("read-back mismatch at stub")
        print("stub @0x%08x: %s" % (STUB, " ".join("0x%08x" % w for w in stub)))
        print("call: 0x%08x -> 0x%08x" % (head_old, head_new))

    print("wrote %s (%d bytes)" % (DST, os.path.getsize(DST)))
    print("sha256 %s" % hashlib.sha256(open(DST, "rb").read()).hexdigest())


if __name__ == "__main__":
    main()
