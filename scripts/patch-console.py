#!/usr/bin/env python3
"""Bypass Sony's ADC/errind console gate so PL011 serial output works in QEMU.

pl011_console_setup normally copies the "console enabled" flag from Sony's
amba_ports+4, which is set only by em_amba2_console_enable after the errind
code reads a board ADC strap.  QEMU has no such ADC, so the flag stays 0 and
pl011_console_write returns without sending a byte (register writes happen,
but UARTDR is never written).

At VA 0x602988cc the setup code does `str r3, [r6, #0xd4]`.  r2 already holds
1 at that point; storing r2 instead makes the PL011 console write
unconditionally.

Original: 0xe58630d4  (str r3, [r6, #0xd4])
Patch:    0xe58620d4  (str r2, [r6, #0xd4])

Usage: patch-console.py [src] [dst]
"""
import hashlib
import os
import shutil
import struct
import sys

D = os.path.expanduser("~/firmware/a7m3")
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(D, "vmlinux-atagfix.bin")
DST = sys.argv[2] if len(sys.argv) > 2 else os.path.join(D, "vmlinux-console.bin")

BASE = 0x60108000
VA = 0x602988CC
ORIG = 0xE58630D4
NEW = 0xE58620D4


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
        sys.exit("unexpected instruction; refusing to patch")
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
