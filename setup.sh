#!/bin/bash
# Build QEMU (ma1co/qemu + a7m3 patch) inside this directory.
# Run in WSL/Linux.  setup.ps1 does this for Windows users.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
QEMU_COMMIT=1909382c0d3533051cead7fde70ca8e84807ee14
SRC="$HERE/qemu-src"
BUILD="$HERE/qemu-build"
PATCH="$HERE/patches/qemu-a7m3.patch"

need() {
    command -v "$1" >/dev/null 2>&1 || { echo "缺少命令: $1" >&2; exit 1; }
}
for t in git make gcc pkg-config python3; do need "$t"; done

if ! pkg-config --exists glib-2.0 || ! pkg-config --exists pixman-1; then
    echo "缺少 QEMU 构建依赖。Ubuntu/Debian 请先运行：" >&2
    echo "  sudo apt install build-essential git pkg-config libglib2.0-dev libpixman-1-dev zlib1g-dev ninja-build python3" >&2
    exit 1
fi

if [ ! -d "$SRC/.git" ]; then
    echo "cloning ma1co/qemu ..."
    git clone https://github.com/ma1co/qemu.git "$SRC"
fi

cd "$SRC"
git checkout -f "$QEMU_COMMIT"
if git apply --check "$PATCH" 2>/dev/null; then
    git apply "$PATCH"
else
    echo "QEMU 补丁应用失败（源码 commit 不对？）" >&2
    exit 1
fi

mkdir -p "$BUILD"
cd "$BUILD"
"$SRC/configure" --target-list=arm-softmmu --disable-werror \
    --disable-sdl --disable-gtk
make -j"$(nproc)"

echo ""
echo "QEMU 构建完成: $BUILD/arm-softmmu/qemu-system-arm"
