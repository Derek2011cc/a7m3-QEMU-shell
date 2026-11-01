# a7m3-QEMU

在 QEMU 里启动 Sony **ILCE-7M3（A7M3）** 原厂固件，进入相机的 BusyBox shell。

本项目目标很明确：**能使用虚拟机里的相机 shell**（`/ #`）。
不包含菜单渲染、GPU 模拟或拍摄链。

> **不包含任何 Sony 固件/密钥。** 你需要自己准备 A7M3 4.03 的服务模式分区转储。

## 它能做什么

- 用 QEMU 的 `cxd90045` 机器启动 4.03 内核 + 相机 rootfs；
- 自动挂载 `nflasha` 分区、加载相机模块；
- 进入 Sony 的异常监视器后，输入 `exit` 即可得到 `/ #`；
- 默认提供**浏览器串口终端**（无需 WSLg/图形界面）；
- 也支持在终端里用 `-serial stdio` 直接操作。

## 工作原理

```
ma1co/qemu (cxd90045) + a7m3 补丁（ATAGS / PGD / console）
        +
vmlinux-console.bin（从 nflasha3 的 VMLINUX.BIN 打补丁）
initrd-qemu.img（从 INITRD.IMG 打补丁）
qemu-emmc-2g.img（25 个分区合成的 2 GiB eMMC）
        ↓
QEMU 串口 → 浏览器终端（web/serial_http.py）
```

`run.sh` 会自动设置 `A7M3_LIRO_AUTOREADY=1`（跳过 LIRO 忙等）和
`A7M3_NO_GFX_CONSOLE=1`（不建图形 console）。

## 目录

```
setup.cmd / setup.ps1 / setup.sh   构建 QEMU（克隆 ma1co/qemu + 打补丁）
import.cmd / import.ps1 / import.sh 从服务模式转储生成启动文件
run.cmd / run.ps1 / run.sh          启动（web 浏览器终端 / stdio）
web/serial_http.py                  串口 → HTTP 终端
patches/qemu-a7m3.patch             QEMU 补丁
scripts/                            内核/initrd/eMMC 处理脚本
firmware/                           生成物 + service-dump（gitignore）
qemu-src/ qemu-build/               源码与构建目录（gitignore）
```

## 快速开始（Windows）

### 1. 安装 WSL2

管理员 PowerShell：

```powershell
wsl --install
```

### 2. 构建 QEMU

WSL（Ubuntu）内需要先装构建依赖：

```bash
sudo apt install build-essential git pkg-config libglib2.0-dev \
     libpixman-1-dev zlib1g-dev ninja-build python3 util-linux
```

在项目目录运行：

```powershell
.\setup.cmd
```

会克隆 `ma1co/qemu`（固定 commit）、打补丁、编译 `qemu-system-arm`。
首次约 **10–20 分钟**。

### 3. 准备服务模式转储

把 A7M3 的服务模式分区转储放到：

```
firmware\service-dump\nflasha1.bin
firmware\service-dump\nflasha2.bin
...
```

至少需要 **2、3、7、10、11、12、15、18**，其余有就写入、没有就留空。

转储方法：用 [a7m3-connect-shell](../a7m3-connect-shell) 以只读方式 `pull` 分区；
或使用你已有的 4.03 服务模式 dump。

> 补丁偏移基于 **4.03**；4.04 的 `vmlinux`/`initrd` 可能不同，脚本会校验原始字节并拒绝不匹配的版本。

### 4. 生成启动文件

```powershell
.\import.cmd
```

输出（约 2 GiB）：

```
firmware\vmlinux-console.bin
firmware\initrd-qemu.img
firmware\qemu-emmc-2g.img
```

### 5. 启动

```powershell
.\run.cmd
```

浏览器会自动打开 `http://127.0.0.1:8099/`。

等待 30–60 秒：

1. 内核日志；
2. `Memory: 1024MB 256MB = 1280MB total`；
3. `im.elf` 因 GPU 未模拟失败，出现 `Exception>`；
4. 在输入框输入 **`exit`**，回车；
5. 出现 `/ #`，即可执行命令。

## 快速开始（Linux）

```bash
./setup.sh
# 放入 firmware/service-dump/nflasha*.bin
./import.sh
./run.sh web      # 浏览器终端
# 或
./run.sh stdio    # 当前终端，Ctrl-A X 退出
```

## 启动后验证

```sh
cat /proc/version
cat /proc/partitions     # nflasha1..25
cat /proc/mounts         # /usr /system /setting 已挂载
ls /usr/bin
```

## 已知现象（正常）

- `im.elf` 启动失败并进入 `Exception>`：默认 GPU 打桩的预期行为；
- `dma330` 附近可能停顿约 10 秒；
- 输入 `exit` 后打印 `Good Bye.`，进入 `/ #`；
- 镜像使用 `snapshot=on`，退出后不修改原文件。

## 故障排查

| 现象 | 处理 |
|---|---|
| 完全没有串口输出 | 确认用的是 `vmlinux-console.bin`（不是原始 vmlinux） |
| `setup_arch` Data Abort | 内核补丁顺序/版本不对；重跑 `import.sh` |
| init 被 `sugi_hw.c` 杀死 | 重新生成镜像（`build-emmc.sh` 会调用 `patch-grmgles.py`） |
| `backup.ko` 返回 `-EIO` | initrd 未打补丁；重跑 `import.sh` |
| `upm` NULL 解引用 | QEMU 补丁/内存模型不对；确认补丁已应用 |
| 镜像不是 2,148,007,936 字节 | `dd` 截断；检查 `conv=sparse,notrunc` |
| 浏览器一直黑屏 | 等 60 秒；看 `run.cmd` 窗口是否有 QEMU 报错 |
| `/dev/dmpgles2` 不存在 | 正常；本项目不模拟 GPU |

## 磁盘与时间

- 源码 + 构建：约 1–2 GB；
- eMMC 镜像：约 2 GiB；
- 首次构建 QEMU：10–20 分钟（8 核）。

## 安全与边界

- 只处理**只读**服务模式转储；不改真机、不写相机分区；
- 不包含 Sony 固件、密钥或转储；
- 这是研究/调试用途，不是完整相机模拟器。

## 致谢

- [ma1co/qemu](https://github.com/ma1co/qemu) — `cxd90045` 机器与 BIONZ 设备模型，本项目的基座；
- [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) — 服务模式 USB 协议与认证实现；
- [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) — Sony 固件包解析；
- [QEMU](https://www.qemu.org/) — 全系统模拟器；
- 前序 A7M3 逆向报告（本仓库 `report/2026-10-17-qemu-native-camera/a7m3`）— 启动链、补丁脚本与踩坑记录；
- [a7m3-connect-shell](../a7m3-connect-shell) — 服务模式分区转储工具。

## 许可

本仓库脚本 MIT。QEMU 及其补丁遵循 **GPL-2.0**；`ma1co/qemu` 由 `setup` 单独克隆，不随本仓库分发。
