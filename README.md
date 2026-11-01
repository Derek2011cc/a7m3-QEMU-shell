# a7m3-QEMU

在 QEMU 里启动 Sony **ILCE-7M3（A7M3）** 原厂 4.03 固件，进入相机的 BusyBox shell（`/ #`）。

**下载即可用**：仓库已包含内核、initrd、压缩分片的 eMMC 镜像，以及预编译 QEMU；
首次运行会自动还原镜像并启动，不需要自己准备固件或编译。

> **版权提示**：`firmware/` 中的 Sony 固件/转储来自研究者的自有设备，仅供个人研究。
> 公开分发可能涉及 Sony 的版权；请在遵守当地法律的前提下使用。本项目与 Sony 无关。

## 它能做什么

- 启动 4.03 内核 + 相机 rootfs，自动挂载 `nflasha` 分区、加载模块；
- 进入 Sony 异常监视器后输入 `exit`，或直接得到 `/ #`；
- 默认提供**浏览器串口终端**（无需 WSLg/图形界面）；
- 也支持终端里的 `-serial stdio`。

不含菜单渲染、GPU 模拟、拍摄链。

## 工作原理

```
firmware/image/part-*  --assemble.sh-->  qemu-emmc-2g.img (2 GiB)
        +
vmlinux-console.bin / initrd-qemu.img
        +
qemu-prebuilt/qemu-system-arm  (cxd90045 + a7m3 补丁)
        ↓
QEMU 串口 → web/serial_http.py → 浏览器终端
```

`run.sh` 会自动设置 `A7M3_LIRO_AUTOREADY=1`（跳过 LIRO 忙等）和
`A7M3_NO_GFX_CONSOLE=1`（不建图形 console）。

## 目录

```
run.cmd / run.ps1 / run.sh          启动（web 浏览器终端 / stdio）
assemble.sh                         从分片还原 2 GiB eMMC 镜像（首次运行自动）
qemu-prebuilt/qemu-system-arm       预编译 QEMU（Ubuntu 24.04，headless）
firmware/                           内核、initrd、镜像分片（已包含）
firmware/image/part-*               gzip 分片，约 127 MB
setup.cmd / setup.ps1 / setup.sh    可选：从源码构建 QEMU
import.cmd / import.ps1 / import.sh 可选：用自己的服务模式转储重新生成
web/serial_http.py                  串口 → HTTP 终端
patches/qemu-a7m3.patch             QEMU 补丁
scripts/                            内核/initrd/eMMC 处理脚本
docs/TECHNICAL.md                   启动链、内存、镜像布局、校验值
qemu-src/ qemu-build/               源码与构建目录（gitignore）
```

## 快速开始（Windows）

### 1. 安装 WSL2

管理员 PowerShell：

```powershell
wsl --install
```

装完重启一次。

### 2. 直接运行

```powershell
.\run.cmd
```

它会：

1. 首次运行时把 `firmware\image\part-*` 还原成 `firmware\qemu-emmc-2g.img`（约 2 GiB）；
2. 使用仓库里的 `qemu-prebuilt/qemu-system-arm` 启动；
3. 打开 `http://127.0.0.1:8099/`。

等待 30–60 秒：

1. 内核日志；
2. `Memory: 1024MB 256MB = 1280MB total`；
3. 若出现 `Exception>`，在输入框输入 **`exit`** 回车；
4. 出现 `/ #`，即可执行命令。

### 如果预编译 QEMU 不能运行

不同发行版的 glibc/依赖可能不兼容。此时构建一次：

```powershell
.\setup.cmd
.\run.cmd
```

WSL（Ubuntu）内需要：

```bash
sudo apt install build-essential git pkg-config libglib2.0-dev \
     libpixman-1-dev zlib1g-dev ninja-build python3 util-linux
```

首次构建约 **10–20 分钟**。

## 快速开始（Linux）

```bash
./run.sh web      # 浏览器终端；首次会自动 assemble
# 或
./run.sh stdio    # 当前终端，Ctrl-A X 退出
```

如果预编译二进制不可用：

```bash
./setup.sh
./run.sh web
```

## 固件与校验

| 文件 | 大小 | SHA-256 |
|---|---|---|
| `firmware/vmlinux-console.bin` | 4,117,760 | `e6c17a94b813111d3a70b95f303d60c07b40da399146a4c0038d075976169b0f` |
| `firmware/initrd-qemu.img` | 2,178,048 | `ec4dc5c97219a282d1d93087ade79d1de962d3c1d6bdde0e715510a2b31b4eb8` |
| `firmware/qemu-emmc-2g.img`（组装后） | 2,148,007,936 | `09968392938a48526b4b37d6d6393c24931c78b8eee47e4067d9275fb16dd50e` |

镜像以 gzip 压缩后按 90 MB 分片（`firmware/image/part-*`，约 127 MB）。
`assemble.sh` 用 `cat part-* | gzip -dc` 还原；已验证还原文件哈希一致。

## 启动后验证

```sh
cat /proc/version
cat /proc/partitions     # nflasha1..25
cat /proc/mounts         # /usr /system /setting 已挂载
ls /usr/bin
```

## 已知现象（正常）

- `im.elf` 启动失败并进入 `Exception>`：默认 GPU 打桩的预期行为；
- 如果没有出现 `Exception>`，shell 可能已经在后台运行，直接输入命令即可；
- `dma330` 附近可能停顿约 10 秒；
- 输入 `exit` 后打印 `Good Bye.`，进入 `/ #`；
- 镜像使用 `snapshot=on`，退出后不修改原文件。

## 故障排查

| 现象 | 处理 |
|---|---|
| 浏览器一直黑屏 | 等 60 秒；看 `run.cmd` 窗口里 QEMU 是否报错 |
| `缺少 qemu-system-arm` | 预编译不可用，运行 `setup.cmd` |
| 完全没有串口输出 | 确认用的是 `vmlinux-console.bin` |
| `setup_arch` Data Abort | 内核补丁/版本不对；用自己的 dump 重新 `import` |
| init 被 `sugi_hw.c` 杀死 | 重新生成镜像（`build-emmc.sh` 会打 GPU 桩） |
| `backup.ko` 返回 `-EIO` | initrd 未打补丁；重新 `import.sh` |
| 镜像不是 2,148,007,936 字节 | 分片不完整；重新下载或 `assemble.sh` |

## 自定义转储（可选）

如果你想用自己的 4.03 服务模式转储重新生成（而不是用仓库里的镜像）：

```powershell
# 把 nflasha*.bin 放到 firmware\service-dump\
.\import.cmd
```

至少需要分区 **2、3、7、10、11、12、15、18**。转储可用
[../a7m3-connect-shell](../a7m3-connect-shell) 只读 `pull`。

## 磁盘与时间

- 仓库约 200 MB（镜像分片 127 MB + 预编译 QEMU 64 MB + 其他）；
- 首次运行会在 `firmware/` 生成 2 GiB 镜像；
- 源码构建另需 1–2 GB 和 10–20 分钟。

## 安全与边界

- 只处理只读转储；不改真机、不写相机分区；
- 不含拍摄链/GPU 模拟，不是完整相机模拟器；
- 固件版权与分发风险由使用者承担。

## 技术细节

启动链、内存映射、ATAGS、镜像分区表、补丁语义、校验值：
见 [docs/TECHNICAL.md](docs/TECHNICAL.md)。

## 致谢

- [ma1co/qemu](https://github.com/ma1co/qemu) — `cxd90045` 机器与 BIONZ 设备模型；
- [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) — 服务模式 USB 协议与认证；
- [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) — Sony 固件包解析；
- [QEMU](https://www.qemu.org/) — 全系统模拟器；
- 前序 A7M3 逆向报告（本仓库 `report/2026-10-17-qemu-native-camera/a7m3`）— 启动链、补丁脚本与踩坑记录；
- [a7m3-connect-shell](../a7m3-connect-shell) — 服务模式分区转储工具。

## 许可

本仓库脚本 MIT。QEMU 及其补丁遵循 **GPL-2.0**；预编译 QEMU 由
`patches/qemu-a7m3.patch` 构建，源码见 `setup.sh` 的固定 commit。
Sony 固件/转储不属于上述开源许可。
