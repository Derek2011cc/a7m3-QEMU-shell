#!/bin/bash
# Build the synthetic 2 GiB eMMC image used to boot the ILCE-7M3 firmware
# under QEMU's cxd90045 machine.
#
# Layout: 0x80000-byte prefix (2 x 256 KiB boot partitions) + 2 GiB user area.
# QEMU's SD model maps the user area at 2*boot_size = 0x80000, so the MBR
# lives at file offset 0x80000, not at the start of the file.
#
# Input:  $D/service-dump/nflashaN.bin (read-only service-mode dump)
# Output: $D/qemu-emmc-2g.img
#
# Usage: build-emmc.sh [data-dir]     (default: $HOME/firmware/a7m3)
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
D="${1:-$HOME/firmware/a7m3}"
DUMP="$D/service-dump"
U="$D/qemu-emmc-user.img"
F="$D/qemu-emmc-2g.img"
USER_SECTORS=4194304          # 2 GiB user area (power of two)
BOOT_OFF=524288               # 0x80000 = 2 * boot_size (0x40000)
BOOT_OFF_SECTORS=$((BOOT_OFF / 512))
MBR_DUMP=$(mktemp)
trap 'rm -f "$MBR_DUMP" "$U"' EXIT

for n in 2 3 7 10 11 12 15 18; do
  [ -f "$DUMP/nflasha$n.bin" ] || {
    echo "missing $DUMP/nflasha$n.bin" >&2
    exit 1
  }
done

rm -f "$U" "$F"
truncate -s $((USER_SECTORS * 512)) "$U"

# Partition sizes come from service-dump/MANIFEST.md (512-byte sectors).
# 4 is the extended container; the SD model has no nflasha4 content anyway.
sfdisk "$U" <<'EOF'
label: dos
unit: sectors

1 : size=16256, type=0x0b
2 : size=40960, type=0x0b
3 : size=98304, type=0x0b
4 : size=3000000, type=0x05
5 : size=122880, type=0x83
6 : size=32768, type=0x83
7 : size=16384, type=0x83
8 : size=16384, type=0x83
9 : size=16384, type=0x83
10 : size=24576, type=0x0b
11 : size=1024000, type=0x0b
12 : size=81920, type=0x0b
13 : size=8192, type=0x83
14 : size=8192, type=0x83
15 : size=614400, type=0x83
16 : size=286720, type=0x83
17 : size=204800, type=0x83
18 : size=40960, type=0x0b
19 : size=8192, type=0x83
20 : size=8192, type=0x83
21 : size=8192, type=0x83
22 : size=8192, type=0x83
23 : size=8192, type=0x83
24 : size=8192, type=0x83
25 : size=8192, type=0x83
EOF

sfdisk -d "$U" > "$MBR_DUMP"

truncate -s $((BOOT_OFF + USER_SECTORS * 512)) "$F"
dd if="$U" of="$F" bs=1M iflag=fullblock oflag=seek_bytes seek=$BOOT_OFF \
   conv=sparse,notrunc status=none
rm -f "$U"

start_of() {
  local n="$1" line
  line=$(grep -E "img${n} : start=" "$MBR_DUMP" | head -1 || true)
  [ -n "$line" ] || return 0
  printf '%s\n' "$line" | sed -n 's/.*start=[[:space:]]*\([0-9][0-9]*\).*/\1/p'
}
size_of() {
  local n="$1" line
  line=$(grep -E "img${n} : start=" "$MBR_DUMP" | head -1 || true)
  [ -n "$line" ] || return 0
  printf '%s\n' "$line" | sed -n 's/.*size=[[:space:]]*\([0-9][0-9]*\).*/\1/p'
}

put_image() {
  local n="$1" f="$DUMP/nflasha$n.bin" s psz isz
  s=$(start_of "$n"); psz=$(size_of "$n")
  [ -n "$s" ] || { echo "partition $n: no start found" >&2; return 1; }
  if [ ! -f "$f" ]; then
    echo "partition $n: placeholder (no image), start=$s"
    return 0
  fi
  isz=$(stat -c %s "$f")
  if [ "$isz" -gt $((psz * 512)) ]; then
    echo "partition $n: image $isz B > partition $((psz * 512)) B" >&2
    return 1
  fi
  echo "partition $n: image $isz B -> lba $s ($psz sectors)"
  dd if="$f" of="$F" bs=1M oflag=seek_bytes seek=$((BOOT_OFF + s * 512)) \
     conv=sparse,notrunc status=none
}

for n in 1 2 3 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25; do
  put_image "$n"
done

echo '=== verify MBR at user-area offset ==='
dd if="$F" bs=512 skip=$BOOT_OFF_SECTORS count=1 status=none | od -A x -t x1 | head -4
sig=$(dd if="$F" bs=1 skip=$((BOOT_OFF + 510)) count=2 status=none | od -An -tx1 | tr -d ' \n')
if [ "$sig" != "55aa" ]; then
  echo "bad MBR signature at 0x$((BOOT_OFF + 510)): $sig" >&2
  exit 1
fi

S15=$(start_of 15)
[ -n "$S15" ] || { echo "partition 15 start not found" >&2; exit 1; }
echo "nflasha15 starts at lba $S15; final: $(stat -c '%n %s bytes' "$F")"
du -h "$F"

# Skip grm_gles.ko's init_module (Sugilite GPU BUG in QEMU).
# The LBA is passed explicitly so a different sfdisk alignment cannot
# silently point us at the wrong place.
python3 "$HERE/patch-grmgles.py" "$F" --lba "$S15"
