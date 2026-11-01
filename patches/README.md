# QEMU 机器模型补丁

`qemu-a7m3.patch` 是基于 [ma1co/qemu](https://github.com/ma1co/qemu)
revision `1909382c0d3533051cead7fde70ca8e84807ee14` 的 `git diff`，包含
A7M3（CXD90045）在 QEMU 中启动所需的最小改动。

## 应用

```sh
git clone https://github.com/ma1co/qemu.git
cd qemu
git checkout 1909382c0d3533051cead7fde70ca8e84807ee14
git apply /path/to/qemu-a7m3.patch
```

然后在 `build-arm/` 中配置并编译 `arm-softmmu`（见 [../README.md](../README.md)）。

补丁基于上述 revision；更新的 ma1co/qemu 可能已改变行号或上下文，
`git apply` 会报错而不是静默错位。若只需功能部分，可先应用整个补丁再
还原 `hw/char/pl011.c` 与 `target/arm/helper.c`（它们只加日志）。

## 文件说明

### `hw/arm/bionz.c` — 功能改动（必需）

| 改动 | 目的 |
|---|---|
| `CXD90045_DDR1_BASE/SIZE` = `0x80000000` / `0x10000000` | 按**主内核**真实地图恢复 DDR1：256 MiB @ `0x80000000`（不是 updater 的 1016 MiB） |
| 增加 `CXD90045_ATAGS_ADDR` / `CXD90045_CMDLINE` | cmdline 使用主内核 `nflasha2:/kemco.txt` 的 `memrsv`：`1M@0`、`704M@0x14000000:uc`、`14M@0x80000000:uc`、`242M@0x80e00000:uc` 等 |
| 新增 `cxd90045_write_atags()` | 写 size-first ATAGS：CORE/MEM(×2)/CMDLINE/INITRD2/NONE |
| 新增 `cxd_write_bootloader_with_machine()` | 引导桩设置 `r0=0, r1=0x11a, r2=ATAGS` |
| 内核加载前预置 16 KiB 页表到 PA `0x00104000` | `pgd[0x600]=0x00011c0e`，让 `setup_arch` 能读 ATAGS |
| `bootrom` 改为可写 RAM `vectors` | Linux 使用 high vectors，会写 `0xffff0000` |
| `bionz_bootcon` 不再占用 serial0 | serial0 留给 PL011 作为 Linux 控制台 |
| `load_image_targphys` 记录 initrd 大小并传入 ATAGS | `ATAG_INITRD2` 需要准确的 size |
| `A7M3_LIRO_AUTOREADY=1` 环境变量 | 让 LIRO/CP 的忙等直接通过（否则启动停在 `entry_main`） |
| `A7M3_NO_GFX_CONSOLE=1` 环境变量 | 跳过图形 console，纯 headless 运行 |

页表写入后会从 PA `0x00105800` 读回并打印，这是写入成功的证据。

> 内存参数来源：`nflasha2:/kemco.txt`（主内核，1,901 B），不是
> `nflasha1/BOOT/KEMCO.TXT`（updater/recovery，815 B）。两者的 DDR1 大小
> 和 `uc` 区间不同。
>
> 该模型只复现 `memrsv` 对非缓存地址表/保留区的语义；`wbi_memclr`、
> `wbimem`、`pm.*` 与 `0xf2a1xxxx` 硬件块尚未模拟。

### `hw/char/pl011.c` — 调试日志（可去掉）

对前 400 次寄存器写、前 200 次 `UARTFR` 读和前 200 次 `UARTDR` 写打印
`A7M3-PL011-*` 到 QEMU 的 stderr。它不影响客户机行为；排查“串口无输出”
时用来区分“内核没写 DR”与“QEMU 没转发”。

### `target/arm/helper.c` — Data Abort 日志（可去掉）

在 `EXCP_DATA_ABORT` 时打印 PC、DFAR、TTBR0/TTBCR/SCTLR、通用寄存器和
一级页表项。用于定位“ATAGS 读不到/页表被清空”这类早期启动故障。
同时增加 `#include "exec/address-spaces.h"`（读页表项用）。

## 注意

- 这些改动只影响 QEMU 的 `cxd90045` 机器，不影响其它机器或真机。
- 调试日志输出到宿主机的 stderr，不是客户机串口；两者在 `-serial stdio`
  时都显示在终端，但来源不同。
- 补丁不包含任何 Sony 固件、分区数据或生成镜像。
