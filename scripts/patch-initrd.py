#!/usr/bin/env python3
"""Patch the A7M3 initrd (an ext2 image) for QEMU bring-up.

The initrd is mounted as root=/dev/ram0.  Its /sbin/init embeds the kernel
module list and parameters as plain strings, so two same-length byte
replacements are enough (ext2 has no checksums and the size does not change):

  Backup_load=0   -> Backup_load=1
      backup.ko returns -EIO when loading from WBI; the real camera has a
      WBI/dnflasha path that this QEMU setup does not provide.  Backup_load=1
      selects file-based loading from /setting.

  /usr/kmod/udate.ko -> /usr/kmod/udate.zz
      udate_init_clock NULL-dereferences because the UDIF clock is absent.
      Renaming to a missing path makes init skip the module.

The script asserts that each string occurs exactly once, keeps the length
identical, and reads the result back.

Usage: patch-initrd.py [src] [dst]
"""
import hashlib
import os
import struct
import sys

D = os.path.expanduser("~/firmware/a7m3")
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(D, "initrd-4.03.img")
DST = sys.argv[2] if len(sys.argv) > 2 else os.path.join(D, "initrd-qemu.img")

BACKUP_OLD = b"Backup_load=0 "
BACKUP_NEW = b"Backup_load=1 "
UDATE_OLD = b"/usr/kmod/udate.ko"
UDATE_NEW = b"/usr/kmod/udate.zz"


def replace_once(data, old, new, label):
    if len(old) != len(new):
        sys.exit("%s: replacement changes length" % label)
    n_old = data.count(old)
    n_new = data.count(new)
    if n_old == 1 and n_new == 0:
        i = data.find(old)
        data[i:i + len(old)] = new
        print("%s: patched at 0x%x" % (label, i))
        return i
    if n_old == 0 and n_new == 1:
        print("%s: already patched" % label)
        return data.find(new)
    sys.exit("%s: expected exactly one occurrence (old=%d new=%d)"
             % (label, n_old, n_new))


def main():
    if not os.path.isfile(SRC):
        sys.exit("no such file: %s" % SRC)
    data = bytearray(open(SRC, "rb").read())

    # ext2 superblock magic at 1024 + 56.
    if len(data) < 1080 or struct.unpack_from("<H", data, 1080)[0] != 0xEF53:
        sys.exit("%s does not look like an ext2 image" % SRC)

    print("initrd %s (%d bytes)" % (SRC, len(data)))
    off_b = replace_once(data, BACKUP_OLD, BACKUP_NEW, "Backup_load")
    off_u = replace_once(data, UDATE_OLD, UDATE_NEW, "udate path")

    open(DST, "wb").write(data)
    chk = open(DST, "rb").read()
    assert chk.count(BACKUP_OLD) == 0 and chk.count(BACKUP_NEW) == 1
    assert chk.count(UDATE_OLD) == 0 and chk.count(UDATE_NEW) == 1
    assert chk[off_b:off_b + len(BACKUP_NEW)] == BACKUP_NEW
    assert chk[off_u:off_u + len(UDATE_NEW)] == UDATE_NEW

    print("wrote %s (%d bytes)" % (DST, len(chk)))
    print("sha256 %s" % hashlib.sha256(chk).hexdigest())


if __name__ == "__main__":
    main()
