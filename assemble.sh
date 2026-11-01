#!/bin/bash
# Rebuild firmware/qemu-emmc-2g.img from the compressed split parts.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
D="${1:-$HERE/firmware}"
IMG="$D/qemu-emmc-2g.img"
PARTS="$D/image"

if [ -f "$IMG" ]; then
    exit 0
fi
if ! ls "$PARTS"/part-* >/dev/null 2>&1; then
    echo "缺少 $PARTS/part-*" >&2
    exit 1
fi

echo "assembling eMMC image from parts ..."
cat "$PARTS"/part-* | gzip -dc > "$IMG"

SIZE=$(stat -c %s "$IMG")
echo "done: $IMG ($SIZE bytes)"
if [ "$SIZE" != "2148007936" ]; then
    echo "warning: expected 2148007936 bytes" >&2
fi
