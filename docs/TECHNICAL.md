# 技术细节

本文说明 A7M3 固件在 QEMU 中启动到 shell 的完整链路、镜像布局、补丁语义和已知边界。

## 1. 启动链

```
QEMU cxd90045 reset
  → bootrom 引导桩：r0=0, r1=0x11a, r2=ATAGS
  → 内核 PA 0x00108000（VA 0x60108000）
  → initrd PA 0x00700000
  → 预置页表 PA 0x00104000（pgd[0x600]=0x00011c0e）
  → Linux setup_arch 读 ATAGS / 页表
  → initrd（ext2）挂载，init 挂载 nflasha 分区、加载模块
  → /usr/bin/im.elf（Appframework）启动
  → GPU 未模拟 → 异常监视器（Exception>）或直接留在 / #
```

关键点：

- 内核链接基址 `0x60108000`，`PAGE_OFFSET=0x60000000`；
- 内核 `stext` 会覆盖 ATAGS 指针，因此有 `patch-atagfix`；
- 内核会清零 `swapper_pg_dir`，因此有 `patch-pgdpatch` 保留 QEMU 预置页表；
- 串口被 Sony ADC/errind 门控，因此有 `patch-console`。

## 2. 内存映射

| 区域 | 地址 | 大小 | 说明 |
|---|---|---|---|
| DDR0 | `0x00000000` | 1 GiB | 内核/initrd/页表/LIRO |
| DDR1 | `0x80000000` | 256 MiB | 主内核地图 |
| ATAGS | `0x00010000` | — | size-first ATAGS |
| 初始页表 | `0x00104000` | 16 KiB | `pgd[0x600]=0x00011c0e` |
| 内核加载 | `0x00108000` | — | `vmlinux-console.bin` |
| initrd | `0x00700000` | — | `initrd-qemu.img` |
| LIRO 固件 | `0x035c6000` | 18.4 MB | `av-cam.bin`（镜像内） |

cmdline 使用主内核 `nflasha2:/kemco.txt` 的 `memrsv`：

```
1M@0, 0x8000@0xF00000, 0x1A5E000@0x02E68000, 0xA6EB000@0x09915000,
704M@0x14000000:uc, 14M@0x80000000:uc, 242M@0x80e00000:uc
```

ATAGS 序列：CORE / MEM×2 / CMDLINE / INITRD2 / NONE。

## 3. QEMU 补丁

补丁见 `patches/qemu-a7m3.patch`，基于 ma1co/qemu
`1909382c0d3533051cead7fde70ca8e84807ee14`。

`hw/arm/bionz.c` 的关键改动：

| 改动 | 目的 |
|---|---|
| DDR1 = `0x80000000` + 256 MiB | 按主内核真实地图 |
| `cxd90045_write_atags()` | 写 size-first ATAGS |
| `cxd_write_bootloader_with_machine()` | 引导桩设置机器号 `0x11a` |
| 预置页表 | `setup_arch` 能读 ATAGS |
| bootrom → 可写 RAM `vectors` | Linux 使用 high vectors |
| `bionz_bootcon` 不占 serial0 | serial0 留给 PL011 控制台 |
| initrd size 传入 ATAGS | `ATAG_INITRD2` 需要准确 size |
| `A7M3_LIRO_AUTOREADY=1` | 跳过 LIRO/CP 忙等（否则停在 `entry_main`） |
| `A7M3_NO_GFX_CONSOLE=1` | 不创建图形 console |

`hw/char/pl011.c` 与 `target/arm/helper.c` 只加调试日志，可去掉。

## 4. eMMC 镜像布局

文件大小 **2,148,007,936** 字节 = `0x80000` 前缀 + 2 GiB 用户区。

- 前缀 `0x80000`：两个 256 KiB boot 分区；
- MBR 位于文件偏移 `0x80000`（SD 模型把用户区映射到 `2*boot_size`）；
- 用户区 2 GiB，25 个分区：

| 分区 | 扇区数 | 类型 | 内容 |
|---|---|---|---|
| 1 | 16256 | 0x0b | boot/updater |
| 2 | 40960 | 0x0b | `kemco.txt`（内存地图） |
| 3 | 98304 | 0x0b | FAT12：`VMLINUX.BIN`、`INITRD.IMG`、LIRO |
| 4 | 3000000 | 0x05 | 扩展容器 |
| 5–9 | 122880 / 32768 / 16384 / 16384 / 16384 | 0x83 | 系统分区 |
| 10–12 | 24576 / 1024000 / 81920 | 0x0b | 数据/媒体 |
| 13–14 | 8192 / 8192 | 0x83 | 配置 |
| 15 | 614400 | 0x83 | **rootfs（/usr、/system、/setting）** |
| 16–17 | 286720 / 204800 | 0x83 | 模块/资源 |
| 18 | 40960 | 0x0b | 备份 |
| 19–25 | 8192 ×7 | 0x83 | 其他 |

`build-emmc.sh` 还会调用 `patch-grmgles.py`，把 `grm_gles.ko` 的
`init_module` 打桩（QEMU 不模拟 Sugilite GPU）。

## 5. 内核/initrd 补丁

| 脚本 | 位置 | 改动 |
|---|---|---|
| `patch-pgdpatch.py` | `0x60108068` | `b` 跳过页表清零 |
| `patch-atagfix.py` | `0x60108028` | 改调桩 `0x60495f40` |
| `patch-console.py` | `0x602988cc` | `str r3` → `str r2` |
| `patch-initrd.py` | initrd 内 | `Backup_load=0` → `1`；`udate.ko` → `udate.zz` |

所有补丁都先校验原始字节，不匹配就拒绝写入。

## 6. 串口与终端

- QEMU 使用 TCP chardev：`-serial tcp:127.0.0.1:4444,server=on,wait=off`；
- `web/serial_http.py` 连接该 TCP，提供 `http://127.0.0.1:8099/` 终端；
- 浏览器输入回车发送 `\r`，页面每 400 ms 拉取增量输出；
- 也可以 `./run.sh stdio`，用 Ctrl-A X 退出。

## 7. 固件文件与校验值

| 文件 | 大小 | SHA-256 |
|---|---|---|
| `firmware/vmlinux-console.bin` | 4,117,760 | `e6c17a94b813111d3a70b95f303d60c07b40da399146a4c0038d075976169b0f` |
| `firmware/initrd-qemu.img` | 2,178,048 | `ec4dc5c97219a282d1d93087ade79d1de962d3c1d6bdde0e715510a2b31b4eb8` |
| `firmware/qemu-emmc-2g.img`（组装后） | 2,148,007,936 | `09968392938a48526b4b37d6d6393c24931c78b8eee47e4067d9275fb16dd50e` |

镜像以 gzip 压缩后按 90 MB 分片存放在 `firmware/image/part-*`（约 127 MB），
`assemble.sh` 用 `cat part-* | gzip -dc` 还原；已验证还原文件哈希一致。

## 8. 已知边界

- Sugilite GPU 未模拟：`/dev/dmpgles2` 不存在，`im.elf` 可能崩溃并进入
  `Exception>`；输入 `exit` 后得到 `/ #`；
- 不包含菜单渲染、CMOS/镜头/编码器；
- 只针对 A7M3 4.03；4.04 的 `vmlinux`/`initrd` 偏移可能不同；
- 预编译 QEMU 在 Ubuntu 24.04 上构建，其他发行版若缺库请用 `setup.sh` 重建。

## 9. 重新生成

```bash
./import.sh /path/to/firmware /path/to/service-dump
```

需要 `nflasha2/3/7/10/11/12/15/18.bin`（其余可选），并安装
`util-linux`（`sfdisk`）。
