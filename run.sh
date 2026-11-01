#!/bin/bash
# Boot the A7M3 firmware under QEMU.
#
#   ./run.sh web     (default) headless QEMU + browser terminal on :8099
#   ./run.sh stdio   serial console in the current terminal (Ctrl-A X to quit)
#
# Environment:
#   A7M3_DATA      firmware directory (default: ./firmware)
#   QEMU_BINARY    override; default: ./qemu-prebuilt/qemu-system-arm,
#                  otherwise ./qemu-build/arm-softmmu/qemu-system-arm
#   A7M3_WEB_PORT  web terminal port (default: 8099)
set -euo pipefail

# The patched cxd90045 model needs these:
#   A7M3_LIRO_AUTOREADY=1  skip LIRO/CP busy-wait (otherwise boot stops at
#                          "entry_main")
#   A7M3_NO_GFX_CONSOLE=1  do not create a graphical console (headless)
export A7M3_LIRO_AUTOREADY=1
export A7M3_NO_GFX_CONSOLE=1

HERE=$(cd "$(dirname "$0")" && pwd)
D="${A7M3_DATA:-$HERE/firmware}"
MODE="${1:-web}"

# Firmware image is shipped compressed in firmware/image/part-*.
if [ ! -f "$D/qemu-emmc-2g.img" ] && [ -d "$D/image" ]; then
    bash "$HERE/assemble.sh" "$D"
fi

if [ -n "${QEMU_BINARY:-}" ]; then
    QEMU="$QEMU_BINARY"
elif [ -x "$HERE/qemu-prebuilt/qemu-system-arm" ]; then
    QEMU="$HERE/qemu-prebuilt/qemu-system-arm"
else
    QEMU="$HERE/qemu-build/arm-softmmu/qemu-system-arm"
fi

for f in vmlinux-console.bin initrd-qemu.img qemu-emmc-2g.img; do
    if [ ! -f "$D/$f" ]; then
        echo "缺少 $D/$f（先运行 ./assemble.sh 或 ./import.sh）" >&2
        exit 1
    fi
done
if [ ! -x "$QEMU" ]; then
    echo "缺少 QEMU: $QEMU（运行 ./setup.sh 构建，或用 qemu-prebuilt/）" >&2
    exit 1
fi

ARGS=(
    -M cxd90045
    -kernel "$D/vmlinux-console.bin"
    -initrd "$D/initrd-qemu.img"
    -drive "if=mtd,file=$D/qemu-emmc-2g.img,format=raw,snapshot=on"
    -display none
    -monitor none
    -no-reboot
    -no-shutdown
)

if [ "$MODE" = "stdio" ]; then
    exec "$QEMU" "${ARGS[@]}" -serial stdio
fi

PORT="${A7M3_WEB_PORT:-8099}"
SERIAL_PORT="${A7M3_SERIAL_PORT:-4444}"

"$QEMU" "${ARGS[@]}" -serial "tcp:127.0.0.1:$SERIAL_PORT,server=on,wait=off" &
QPID=$!
python3 "$HERE/web/serial_http.py" --port "$PORT" --serial-port "$SERIAL_PORT" &
WPID=$!
trap 'kill $QPID $WPID 2>/dev/null || true' INT TERM

echo ""
echo "浏览器打开: http://127.0.0.1:$PORT/"
echo "启动后等待 30-60 秒；出现 Exception> 时输入 exit 进入 / #"
echo "按 Ctrl+C 结束。"
wait $QPID || true
kill $WPID 2>/dev/null || true
