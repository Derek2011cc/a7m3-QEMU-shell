#!/bin/bash
# Build the bootable firmware set from a service-mode dump.
#
# Input:  firmware/service-dump/nflasha1.bin ... nflasha25.bin
# Output: firmware/vmlinux-console.bin
#         firmware/initrd-qemu.img
#         firmware/qemu-emmc-2g.img
#
# Usage: ./import.sh [data-dir] [dump-dir]
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
D="${1:-$HERE/firmware}"
DUMP="${2:-$D/service-dump}"
S="$HERE/scripts"

for n in 2 3 7 10 11 12 15 18; do
    if [ ! -f "$DUMP/nflasha$n.bin" ]; then
        echo "缺少 $DUMP/nflasha$n.bin" >&2
        echo "请先用 a7m3-connect-shell 做服务模式分区转储（只读）。" >&2
        exit 1
    fi
done

mkdir -p "$D"

echo "== 提取内核与 initrd (nflasha3 FAT12) =="
python3 "$S/fat-extract.py" "$DUMP/nflasha3.bin" >/dev/null || true
python3 "$S/fat-extract.py" "$DUMP/nflasha3.bin" VMLINUX.BIN -o "$D/vmlinux.bin"
python3 "$S/fat-extract.py" "$DUMP/nflasha3.bin" INITRD.IMG -o "$D/initrd-4.03.img"

echo "== 打内核补丁 =="
python3 "$S/patch-pgdpatch.py" "$D/vmlinux.bin" "$D/vmlinux-pgdpatch.bin"
python3 "$S/patch-atagfix.py" "$D/vmlinux-pgdpatch.bin" "$D/vmlinux-atagfix.bin"
python3 "$S/patch-console.py" "$D/vmlinux-atagfix.bin" "$D/vmlinux-console.bin"

echo "== 打 initrd 补丁 =="
python3 "$S/patch-initrd.py" "$D/initrd-4.03.img" "$D/initrd-qemu.img"

echo "== 生成 2 GiB eMMC 镜像 =="
bash "$S/build-emmc.sh" "$D"

echo ""
echo "导入完成：$D"
echo "  vmlinux-console.bin"
echo "  initrd-qemu.img"
echo "  qemu-emmc-2g.img"
