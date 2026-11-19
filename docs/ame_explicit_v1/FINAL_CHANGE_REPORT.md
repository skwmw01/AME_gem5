# xuantie-v0.6、spec-v0.5a 双独立显式子集最终修改报告

## 1. 实现结论

总验收状态：**PASS**；检查汇总：`{'PASS': 58}`。
基线：`6677b2c8f6e76363050427009d47c5481f9e53bf`；分支：`ztt0.6-xuantie0.6-spec0.5a-vs`。
实现内容指纹（源文件 SHA256 清单的 SHA256）：`a596677a26feca0ae93859f9c315d50ae42c45ad607ec7ad50a289b972989e81`。
指纹包含新增文件，不依赖提交或暂存状态；生成报告与证据不参与自身哈希。

两组各十条研究性显式计算指令，分别拥有译码、指令类、运算循环、数值包装和参考适配。
两个编译开关默认关闭；不实现两份原生 ISA 的二进制兼容。
仅修改六个原有模拟器入口，新增八个模拟器源文件。旧 Ztt、CSR、寄存器定义、CPU/FU 和 example 源码未修改。

证据入口：[验收清单](evidence/acceptance.json)、[构建](evidence/build_matrix.json)、
[独立性](evidence/independence.json)、[回归](evidence/regression.json)、[哈希清单](evidence/manifest.json)。
证据中的 results 路径指向本地保留的原始运行；本目录 evidence 保留对应的紧凑 JSON、命令日志及哈希。

## 2. 修改清单

| 文件 | 状态 | +行 / -行 |
|---|---|---|
| `results/.gitignore` | 新增 | 2 / 0 |
| `src/arch/riscv/Kconfig` | 修改 | 10 / 0 |
| `src/arch/riscv/SConscript` | 修改 | 5 / 0 |
| `src/arch/riscv/insts/spec_v05a_explicit.cc` | 新增 | 201 / 0 |
| `src/arch/riscv/insts/spec_v05a_explicit.hh` | 新增 | 28 / 0 |
| `src/arch/riscv/insts/xuantie_v06_explicit.cc` | 新增 | 177 / 0 |
| `src/arch/riscv/insts/xuantie_v06_explicit.hh` | 新增 | 26 / 0 |
| `src/arch/riscv/isa/decoder.isa` | 修改 | 2 / 0 |
| `src/arch/riscv/isa/decoder/spec_v05a_explicit.isa` | 新增 | 29 / 0 |
| `src/arch/riscv/isa/decoder/xuantie_v06_explicit.isa` | 新增 | 26 / 0 |
| `src/arch/riscv/isa/formats/formats.isa` | 修改 | 3 / 0 |
| `src/arch/riscv/isa/formats/spec_v05a_explicit.isa` | 新增 | 55 / 0 |
| `src/arch/riscv/isa/formats/xuantie_v06_explicit.isa` | 新增 | 44 / 0 |
| `src/arch/riscv/isa/includes.isa` | 修改 | 12 / 0 |
| `src/arch/riscv/isa/operands.isa` | 修改 | 13 / 0 |
| `tests/ame_explicit_v1/README.md` | 新增 | 118 / 0 |
| `tests/ame_explicit_v1/common/acceptance.py` | 新增 | 118 / 0 |
| `tests/ame_explicit_v1/common/checkpoint_config.py` | 新增 | 19 / 0 |
| `tests/ame_explicit_v1/common/checkpoint_guest.c` | 新增 | 49 / 0 |
| `tests/ame_explicit_v1/common/compile_compat.py` | 新增 | 10 / 0 |
| `tests/ame_explicit_v1/common/decode_fields.py` | 新增 | 57 / 0 |
| `tests/ame_explicit_v1/common/edge_generate.py` | 新增 | 32 / 0 |
| `tests/ame_explicit_v1/common/edge_guest.c` | 新增 | 57 / 0 |
| `tests/ame_explicit_v1/common/extra_tests.py` | 新增 | 24 / 0 |
| `tests/ame_explicit_v1/common/fault_injection.sh` | 新增 | 48 / 0 |
| `tests/ame_explicit_v1/common/generate.py` | 新增 | 111 / 0 |
| `tests/ame_explicit_v1/common/guest.c` | 新增 | 114 / 0 |
| `tests/ame_explicit_v1/common/ieee.py` | 新增 | 101 / 0 |
| `tests/ame_explicit_v1/common/incremental.sh` | 新增 | 20 / 0 |
| `tests/ame_explicit_v1/common/inspect_build.py` | 新增 | 37 / 0 |
| `tests/ame_explicit_v1/common/interleave.c` | 新增 | 43 / 0 |
| `tests/ame_explicit_v1/common/reporting.py` | 新增 | 287 / 0 |
| `tests/ame_explicit_v1/common/runtime.c` | 新增 | 391 / 0 |
| `tests/ame_explicit_v1/common/shape.py` | 新增 | 58 / 0 |
| `tests/ame_explicit_v1/common/storage.py` | 新增 | 59 / 0 |
| `tests/ame_explicit_v1/common/trap.S` | 新增 | 26 / 0 |
| `tests/ame_explicit_v1/regression/README.md` | 新增 | 10 / 0 |
| `tests/ame_explicit_v1/regression/compat.c` | 新增 | 33 / 0 |
| `tests/ame_explicit_v1/run.py` | 新增 | 394 / 0 |
| `tests/ame_explicit_v1/spec_v05a/README.md` | 新增 | 8 / 0 |
| `tests/ame_explicit_v1/spec_v05a/cases.json` | 新增 | 332 / 0 |
| `tests/ame_explicit_v1/spec_v05a/encoding.csv` | 新增 | 11 / 0 |
| `tests/ame_explicit_v1/spec_v05a/encoding.h` | 新增 | 34 / 0 |
| `tests/ame_explicit_v1/spec_v05a/kernels.S` | 新增 | 162 / 0 |
| `tests/ame_explicit_v1/spec_v05a/reference.py` | 新增 | 55 / 0 |
| `tests/ame_explicit_v1/spec_v05a/semantic_contract.md` | 新增 | 30 / 0 |
| `tests/ame_explicit_v1/spec_v05a/spec_mapping.csv` | 新增 | 11 / 0 |
| `tests/ame_explicit_v1/xuantie_v06/README.md` | 新增 | 9 / 0 |
| `tests/ame_explicit_v1/xuantie_v06/cases.json` | 新增 | 332 / 0 |
| `tests/ame_explicit_v1/xuantie_v06/encoding.csv` | 新增 | 11 / 0 |
| `tests/ame_explicit_v1/xuantie_v06/encoding.h` | 新增 | 34 / 0 |
| `tests/ame_explicit_v1/xuantie_v06/kernels.S` | 新增 | 162 / 0 |
| `tests/ame_explicit_v1/xuantie_v06/reference.py` | 新增 | 53 / 0 |
| `tests/ame_explicit_v1/xuantie_v06/semantic_contract.md` | 新增 | 29 / 0 |
| `tests/ame_explicit_v1/xuantie_v06/spec_mapping.csv` | 新增 | 11 / 0 |

模拟器四类操作分别为逐元素加法、最大值、宽化乘加、转换；测试目录含独立编码表、参考模型、来宾程序和验收工具。
上表列出实现与测试文件；本报告和自动生成的 evidence 文件单独作为交付文档。

## 3. 逐条实现与规范对应

| 分组 | 实验指令 | 原规范名称与位置 | mask / match | 执行类 / 函数 | 适配 | 测试 |
|---|---|---|---|---|---|---|
| X06 | `xt06.add.i32` | madd.w.mm · 5.5.1 PDF47-48 | `0xfe00707f` / `0x2000000b` | `Xt06_add_i32` / `X06::add` | fixed 4x4 M and wraparound | XT06-0 |
| X06 | `xt06.add.f32` | mfadd.s.mm · 5.5.2 PDF49-50 | `0xfe00707f` / `0x2000100b` | `Xt06_add_f32` / `X06::add` | fixed RNE and AMEFFLAGS | XT06-1 |
| X06 | `xt06.max.i32` | mmax.w.mm · 5.5.1 PDF47-48 | `0xfe00707f` / `0x2200000b` | `Xt06_max_i32` / `X06::maximum` | fixed 4x4 M | XT06-2 |
| X06 | `xt06.max.u32` | mumax.w.mm · 5.5.1 PDF47-48 | `0xfe00707f` / `0x2200100b` | `Xt06_max_u32` / `X06::maximum` | fixed 4x4 M | XT06-3 |
| X06 | `xt06.macbt.i8.i32` | mmacc.w.b · 5.2.2 PDF26-28 | `0xfe007e7f` / `0x2400000b` | `Xt06_macbt_i8_i32` / `X06::macbt` | fixed BT layout and non-saturating; plan mmaqa.b name corrected against supplied PDF | XT06-4 |
| X06 | `xt06.macbt.f16.f32` | mfmacc.s.h · 5.2.2 PDF26-28 | `0xfe007e7f` / `0x2400100b` | `Xt06_macbt_f16_f32` / `X06::macbt` | fixed BT layout and ordered k FP32 FMA | XT06-5 |
| X06 | `xt06.macbt.bf16.f32` | mfmacc.s.bf16 · 5.2.2 PDF26-28 | `0xfe007e7f` / `0x2400200b` | `Xt06_macbt_bf16_f32` / `X06::macbt` | fixed BT layout and ordered k FP32 FMA | XT06-6 |
| X06 | `xt06.cvt.f32.i32` | msfcvt.s.w · 5.5.3 PDF51-55 | `0xfff0707f` / `0x2600000b` | `Xt06_cvt_f32_i32` / `X06::convert` | fixed RNE | XT06-7 |
| X06 | `xt06.cvt.i32.f32` | mfscvt.w.s · 5.5.3 PDF51-55 | `0xfff0707f` / `0x2600100b` | `Xt06_cvt_i32_f32` / `X06::convert` | experimental clipping and NV without NX on invalid | XT06-8 |
| X06 | `xt06.cvtlo.f32.f16` | mfcvtl.s.h · 5.5.3 PDF51-55 | `0xfff0707f` / `0x2600200b` | `Xt06_cvtlo_f32_f16` / `X06::convert` | fixed four low columns of each 8-half row | XT06-9 |
| S05A | `sp05a.add.i32` | madd.w.mm · 4.5.2 PDF28-30 | `0xfe00707f` / `0x4000005b` | `Sp05a_add_i32` / `S05A::sum` | fixed M instead of native Acc | SP05A-0 |
| S05A | `sp05a.add.f32` | mfadd.f.mm · 4.5.2 PDF28-30 | `0xfe00707f` / `0x4000105b` | `Sp05a_add_f32` / `S05A::sum` | explicit FP32 instead of mtype; RNE | SP05A-1 |
| S05A | `sp05a.max.i32` | mmax.w.mm · 4.5.2 PDF28-30 | `0xfe00707f` / `0x4200005b` | `Sp05a_max_i32` / `S05A::max` | fixed M instead of native Acc | SP05A-2 |
| S05A | `sp05a.max.u32` | mmaxu.w.mm · 4.5.2 PDF28-30 | `0xfe00707f` / `0x4200105b` | `Sp05a_max_u32` / `S05A::max` | fixed M instead of native Acc | SP05A-3 |
| S05A | `sp05a.mac.i8.i32` | mqma.b.mm · 4.5.1 PDF27-28; table29 PDF85 | `0xfe007e7f` / `0x4400005b` | `Sp05a_mac_i8_i32` / `S05A::multiplyAccumulate` | 4x16 by 16x4 row-major; modulo 2^32 | SP05A-4 |
| S05A | `sp05a.mac.f16.f32` | mfwma.hf.mm · 4.5.1 PDF27-28; 6.9 | `0xfe007e7f` / `0x4400105b` | `Sp05a_mac_f16_f32` / `S05A::multiplyAccumulate` | explicit FP16 instead of mtype.mfp16; ordered FMA | SP05A-5 |
| S05A | `sp05a.mac.bf16.f32` | mfwma.hf.mm · 4.5.1 PDF27-28; 6.10 | `0xfe007e7f` / `0x4400205b` | `Sp05a_mac_bf16_f32` / `S05A::multiplyAccumulate` | explicit BF16 instead of mtype.mfp16; ordered FMA | SP05A-6 |
| S05A | `sp05a.cvt.f32.i32` | mfcvt.f.w.m · 4.6 PDF30-34 | `0xfff0707f` / `0x4600005b` | `Sp05a_cvt_f32_i32` / `S05A::cast` | explicit FP32; fixed RNE | SP05A-7 |
| S05A | `sp05a.cvt.i32.f32` | mfcvt.w.f.m · 4.6 PDF30-34 | `0xfff0707f` / `0x4600105b` | `Sp05a_cvt_i32_f32` / `S05A::cast` | experimental clipping and NV without NX on invalid | SP05A-8 |
| S05A | `sp05a.cvt.f32.f16` | mfwcvt.f.hf.m · 4.6 PDF30-34; table32 PDF98 | `0xfff0707f` / `0x4600205b` | `Sp05a_cvt_f32_f16` / `S05A::widenAll` | 32 halves into consecutive M pair; md31 illegal | SP05A-9 |

X06 INT8 原生名称依据用户 PDF 修正为 `mmacc.w.b`；方案中的 `mmaqa.b` 不是该 PDF 的对应名称。

## 4. 编译开关使用与验收

### 4.1 开关含义与使用环境

两个开关定义于 `src/arch/riscv/Kconfig`，仅适用于 RISC-V 构建，默认均为 `n`：

| 开关 | `y` 时启用 | `n` 时行为 |
|---|---|---|
| `USE_XUANTIE_V06_EXPLICIT` | 10 条 `xt06.*` 指令（X06） | 不编译/链接该组执行实现；对应实验机器字触发非法指令 |
| `USE_SPEC_V05A_EXPLICIT` | 10 条 `sp05a.*` 指令（S05A） | 不编译/链接该组执行实现；对应实验机器字触发非法指令 |

这是 **gem5 编译期开关**，配置按构建目录分别保存。修改后必须重新编译，并运行该目录下的 `gem5.opt`；不需要给 `example/ame_config.py` 增加运行时开关。关闭某组不影响原有 Ztt 指令。

下面的 `scons`、测试和运行命令均在仓库根目录执行。本机采用现有 Docker 环境，可先在宿主的仓库根目录进入容器：

```bash
docker run --rm -it -v "$PWD:/work" -w /work ame-gem5-rvv:local bash
```

### 4.2 新建四种独立构建

首次创建构建目录时执行 `defconfig`，随后用 `setconfig` 明确设置两组开关，再编译。以下四种组合可以分别执行；`-j8` 可按可用内存和 CPU 调整。

```bash
# B00：两组均关闭（默认行为）
scons defconfig build/AME_B00 build_opts/RISCV
scons setconfig build/AME_B00 USE_XUANTIE_V06_EXPLICIT=n USE_SPEC_V05A_EXPLICIT=n
scons build/AME_B00/gem5.opt -j8

# B10：仅启用 X06
scons defconfig build/AME_B10 build_opts/RISCV
scons setconfig build/AME_B10 USE_XUANTIE_V06_EXPLICIT=y USE_SPEC_V05A_EXPLICIT=n
scons build/AME_B10/gem5.opt -j8

# B01：仅启用 S05A
scons defconfig build/AME_B01 build_opts/RISCV
scons setconfig build/AME_B01 USE_XUANTIE_V06_EXPLICIT=n USE_SPEC_V05A_EXPLICIT=y
scons build/AME_B01/gem5.opt -j8

# B11：同时启用两组
scons defconfig build/AME_B11 build_opts/RISCV
scons setconfig build/AME_B11 USE_XUANTIE_V06_EXPLICIT=y USE_SPEC_V05A_EXPLICIT=y
scons build/AME_B11/gem5.opt -j8
```

也可用统一入口一次构建并检查四种组合：

```bash
python3 tests/ame_explicit_v1/run.py build-matrix --build-root build --jobs 8
```

### 4.3 已有构建目录切换与关闭

已有目录先执行 `olddefconfig` 接纳新增配置项并保留其他配置，再 `setconfig`。例如，在已有 `build/RISCV` 中启用两组：

```bash
scons olddefconfig build/RISCV
scons setconfig build/RISCV USE_XUANTIE_V06_EXPLICIT=y USE_SPEC_V05A_EXPLICIT=y
scons build/RISCV/gem5.opt -j8
```

仅启用一组时，将另一开关设为 `n`；恢复两组关闭：

```bash
scons setconfig build/RISCV USE_XUANTIE_V06_EXPLICIT=n USE_SPEC_V05A_EXPLICIT=n
scons build/RISCV/gem5.opt -j8
```

不需要手工删除目标文件或修改生成头文件。本版已经验证同一目录关闭→开启→关闭的增量编译。此处命令是使用说明；本次交付时默认 `build/RISCV` 仍为两组关闭。

### 4.4 确认配置并运行对应二进制

实际配置保存在 `<构建目录>/gem5.build/config`。例如检查 B11：

```bash
grep -E 'USE_(XUANTIE_V06|SPEC_V05A)_EXPLICIT' build/AME_B11/gem5.build/config
```

启用时显示 `USE_..._EXPLICIT=y`，关闭时显示 `# USE_..._EXPLICIT is not set`。配置文件表示下一次构建所用设置，因此应确认上述编译成功后再运行：

```bash
# 对双开二进制分别验证两组指令
python3 tests/ame_explicit_v1/run.py functional --suite xuantie_v06 --gem5 build/AME_B11/gem5.opt
python3 tests/ame_explicit_v1/run.py functional --suite spec_v05a --gem5 build/AME_B11/gem5.opt

# 对双关二进制验证非法指令路径
python3 tests/ame_explicit_v1/run.py functional --suite xuantie_v06 --gem5 build/AME_B00/gem5.opt --disabled --random-count 0 --limit 263
python3 tests/ame_explicit_v1/run.py functional --suite spec_v05a --gem5 build/AME_B00/gem5.opt --disabled --random-count 0 --limit 263

# 运行自己的 ELF；将路径替换为实际来宾 ELF 与报告路径
build/AME_B11/gem5.opt -d /work/m5out-explicit example/ame_config.py --cmd '/work/path/to/program.elf /work/path/to/report.txt'
```

`--disabled` 是测试程序的“预期非法指令”检查选项，不会改变 gem5 开关。两组实验助记符的汇编器支持不由这些开关提供；本版测试通过各组 `encoding.csv`、`encoding.h` 和 `kernels.S` 中的原始机器字发码。

### 4.5 本次构建验收结果


| 构建 | X06 / S05A | 编译及链接 | X06 / S05A 行为 | 模拟器 SHA256 |
|---|---|---|---|---|
| B00 | 0 / 0 | PASS | 非法指令 / 非法指令 | `ab6e3680998a4128d7a55a6a5cd2d6e44ad13f01d8ff0dee694c9060a4bb6459` |
| B10 | 1 / 0 | PASS | 执行 / 非法指令 | `39e390b4e7eea0ab27008d78af76fe91d8a7cc3173d749001d0e5636e7412270` |
| B01 | 0 / 1 | PASS | 非法指令 / 执行 | `71f811b6b0d89417fc4cc3ab25b554d460693d771889745d99091ed23a161aea` |
| B11 | 1 / 1 | PASS | 执行 / 执行 | `6ddf3e8b74544dbe52acad7265fec506f54da96fd9c0c02caf25479ef9355ef9` |

每个构建均检查生成类的结构数据操作数、链接符号和实际译码行为。
第五个构建目录使用已有 `build/RISCV`，执行关闭→开启→关闭并保存三次二进制、配置、测试记录。
这是相对方案“临时第五目录”的有意调整，同时验证已有默认目录的增量更新；最终两开关均为关闭。

## 5. 正确性与独立性

| 检查 | 实测执行数（适用时） | 状态 | 证据 |
|---|---|---|---|
| xuantie_v06 full B10 | 28718 | PASS | [xuantie_v06/20261119-085014-AME_B10/functional.json](evidence/xuantie_v06/20261119-085014-AME_B10/functional.json) |
| xuantie_v06 full B11 | 28718 | PASS | [xuantie_v06/20261119-084255-AME_B11/functional.json](evidence/xuantie_v06/20261119-084255-AME_B11/functional.json) |
| xuantie_v06 single/dual equality | — | PASS | `results/ame_explicit_v1/xuantie_v06/20261119-085014-AME_B10`; `results/ame_explicit_v1/xuantie_v06/20261119-084255-AME_B11` |
| xuantie_v06 random/exhaustive coverage | — | PASS | `results/ame_explicit_v1/xuantie_v06/20261119-084255-AME_B11` |
| xuantie_v06 disabled B00 | 526 | PASS | [xuantie_v06/20261119-085015-AME_B00/functional.json](evidence/xuantie_v06/20261119-085015-AME_B00/functional.json) |
| xuantie_v06 disabled B01 | 526 | PASS | [xuantie_v06/20261119-085013-AME_B01/functional.json](evidence/xuantie_v06/20261119-085013-AME_B01/functional.json) |
| xuantie_v06 dependencies | 526 | PASS | [xuantie_v06/20261119-084849-AME_B11/functional.json](evidence/xuantie_v06/20261119-084849-AME_B11/functional.json) |
| xuantie_v06 checkpoint | 20 | PASS | [xuantie_v06/checkpoint.json](evidence/xuantie_v06/checkpoint.json) |
| xuantie_v06 negative_state | 10 | PASS | [xuantie_v06/negative_state.json](evidence/xuantie_v06/negative_state.json) |
| xuantie_v06 shape | 20 | PASS | [xuantie_v06/shape.json](evidence/xuantie_v06/shape.json) |
| xuantie_v06 storage | 20 | PASS | [xuantie_v06/storage.json](evidence/xuantie_v06/storage.json) |
| xuantie_v06 decode_fields | 146432 | PASS | [xuantie_v06/decode_fields.json](evidence/xuantie_v06/decode_fields.json) |
| xuantie_v06 negative/access B00 | 1211 | PASS | [xuantie_v06/20261119-085015-edge-AME_B00/edge.json](evidence/xuantie_v06/20261119-085015-edge-AME_B00/edge.json) |
| xuantie_v06 negative/access B10 | 1211 | PASS | [xuantie_v06/20261119-085014-edge-AME_B10/edge.json](evidence/xuantie_v06/20261119-085014-edge-AME_B10/edge.json) |
| xuantie_v06 negative/access B01 | 1211 | PASS | [xuantie_v06/20261119-085013-edge-AME_B01/edge.json](evidence/xuantie_v06/20261119-085013-edge-AME_B01/edge.json) |
| xuantie_v06 negative/access B11 | 1211 | PASS | [xuantie_v06/20261119-084255-edge-AME_B11/edge.json](evidence/xuantie_v06/20261119-084255-edge-AME_B11/edge.json) |
| spec_v05a full B01 | 24622 | PASS | [spec_v05a/20261119-085013-AME_B01/functional.json](evidence/spec_v05a/20261119-085013-AME_B01/functional.json) |
| spec_v05a full B11 | 24622 | PASS | [spec_v05a/20261119-084255-AME_B11/functional.json](evidence/spec_v05a/20261119-084255-AME_B11/functional.json) |
| spec_v05a single/dual equality | — | PASS | `results/ame_explicit_v1/spec_v05a/20261119-085013-AME_B01`; `results/ame_explicit_v1/spec_v05a/20261119-084255-AME_B11` |
| spec_v05a random/exhaustive coverage | — | PASS | `results/ame_explicit_v1/spec_v05a/20261119-084255-AME_B11` |
| spec_v05a disabled B00 | 526 | PASS | [spec_v05a/20261119-085015-AME_B00/functional.json](evidence/spec_v05a/20261119-085015-AME_B00/functional.json) |
| spec_v05a disabled B10 | 526 | PASS | [spec_v05a/20261119-085014-AME_B10/functional.json](evidence/spec_v05a/20261119-085014-AME_B10/functional.json) |
| spec_v05a dependencies | 526 | PASS | [spec_v05a/20261119-084849-AME_B11/functional.json](evidence/spec_v05a/20261119-084849-AME_B11/functional.json) |
| spec_v05a checkpoint | 20 | PASS | [spec_v05a/checkpoint.json](evidence/spec_v05a/checkpoint.json) |
| spec_v05a negative_state | 10 | PASS | [spec_v05a/negative_state.json](evidence/spec_v05a/negative_state.json) |
| spec_v05a shape | 20 | PASS | [spec_v05a/shape.json](evidence/spec_v05a/shape.json) |
| spec_v05a storage | 20 | PASS | [spec_v05a/storage.json](evidence/spec_v05a/storage.json) |
| spec_v05a decode_fields | 146400 | PASS | [spec_v05a/decode_fields.json](evidence/spec_v05a/decode_fields.json) |
| spec_v05a negative/access B00 | 1212 | PASS | [spec_v05a/20261119-085015-edge-AME_B00/edge.json](evidence/spec_v05a/20261119-085015-edge-AME_B00/edge.json) |
| spec_v05a negative/access B10 | 1212 | PASS | [spec_v05a/20261119-085014-edge-AME_B10/edge.json](evidence/spec_v05a/20261119-085014-edge-AME_B10/edge.json) |
| spec_v05a negative/access B01 | 1212 | PASS | [spec_v05a/20261119-085013-edge-AME_B01/edge.json](evidence/spec_v05a/20261119-085013-edge-AME_B01/edge.json) |
| spec_v05a negative/access B11 | 1212 | PASS | [spec_v05a/20261119-084254-edge-AME_B11/edge.json](evidence/spec_v05a/20261119-084254-edge-AME_B11/edge.json) |
| same mathematical products with distinct B packing | 6 | PASS | `results/ame_explicit_v1/xuantie_v06/20261119-084255-AME_B11`; `results/ame_explicit_v1/spec_v05a/20261119-084255-AME_B11` |
| B00 compile/link/operands | — | PASS | [B00-inspection.json](evidence/B00-inspection.json) |
| B10 compile/link/operands | — | PASS | [B10-inspection.json](evidence/B10-inspection.json) |
| B01 compile/link/operands | — | PASS | [B01-inspection.json](evidence/B01-inspection.json) |
| B11 compile/link/operands | — | PASS | [B11-inspection.json](evidence/B11-inspection.json) |
| incremental off-before | — | PASS | [xuantie_v06/20261119-085846-off-before/functional.json](evidence/xuantie_v06/20261119-085846-off-before/functional.json); [spec_v05a/20261119-085859-off-before/functional.json](evidence/spec_v05a/20261119-085859-off-before/functional.json) |
| incremental on | — | PASS | [xuantie_v06/20261119-090538-on/functional.json](evidence/xuantie_v06/20261119-090538-on/functional.json); [spec_v05a/20261119-090551-on/functional.json](evidence/spec_v05a/20261119-090551-on/functional.json) |
| incremental off-after | — | PASS | [xuantie_v06/20261119-091240-off-after/functional.json](evidence/xuantie_v06/20261119-091240-off-after/functional.json); [spec_v05a/20261119-091253-off-after/functional.json](evidence/spec_v05a/20261119-091253-off-after/functional.json) |
| default switches restored off | — | PASS | `build/RISCV/gem5.build/config` |
| x06 fault isolation | — | PASS | [fault_injection/x06-mutated.json](evidence/fault_injection/x06-mutated.json); [fault_injection/s05-unaffected.json](evidence/fault_injection/s05-unaffected.json) |
| s05 fault isolation | — | PASS | [fault_injection/s05-mutated.json](evidence/fault_injection/s05-mutated.json); [fault_injection/x06-unaffected.json](evidence/fault_injection/x06-unaffected.json) |
| encoding audit | — | PASS | [encoding_audit.json](evidence/encoding_audit.json) |
| interleave P/X06/S05A | — | PASS | [interleave/interleave.json](evidence/interleave/interleave.json) |

完整功能测试每条指令包含种子 0…9、每种子 100 组随机输入及定向边界；两组分别遍历 65,536 种 FP16 位模式。
每个功能用例执行匹配/不匹配描述符两种模式，穿插五种标量 FRM 和后续标量浮点运算。
X06 每构建 28,718 条观测，S05A 每构建 24,622 条；单开与双开来宾报告 SHA256 分别相同。
全寄存器字段实际执行 292,832 次并核对译码 trace。依赖链每组 526 条观测，每条含两个新计算操作。
checkpoint 检查异常前后全部矩阵容器与相关 CSR；storage 检查 72×256 字节物理容器、未使用尾部和非法描述符。
精确有理数 IEEE 参考与模拟器 SoftFloat 独立；两组共享标量参考原语，各自维护布局和计算适配。
双向故障注入各产生 104 条预期失败，仅限被修改组的加法，另一组正向测试仍通过；故障源码不进入本分支。

## 6. 原有功能回归

| 冻结 ELF | B00 | B10 | B01 | B11 | 对照内容 |
|---|---|---|---|---|---|
| compat_rvv_scalar_m5 | PASS | PASS | PASS | PASS | 报告字节、退出状态、最终统计区段 |
| ffn | PASS | PASS | PASS | PASS | 报告字节、退出状态、最终统计区段 |
| gelu | PASS | PASS | PASS | PASS | 报告字节、退出状态、最终统计区段 |
| gemm_fp32 | PASS | PASS | PASS | PASS | 报告字节、退出状态、最终统计区段 |
| gemm_int8 | PASS | PASS | PASS | PASS | 报告字节、退出状态、最终统计区段 |
| gemm_mixed | PASS | PASS | PASS | PASS | 报告字节、退出状态、最终统计区段 |
| gemm_mixed_source_types | PASS | PASS | PASS | PASS | 报告字节、退出状态、最终统计区段 |
| mha | PASS | PASS | PASS | PASS | 报告字节、退出状态、最终统计区段 |
| native_primary_spec_v05a | PASS | PASS | PASS | PASS | 报告字节、退出状态、最终统计区段 |
| native_primary_xuantie_v06 | PASS | PASS | PASS | PASS | 报告字节、退出状态、最终统计区段 |
| rmsnorm | PASS | PASS | PASS | PASS | 报告字节、退出状态、最终统计区段 |
| rope | PASS | PASS | PASS | PASS | 报告字节、退出状态、最终统计区段 |
| softmax | PASS | PASS | PASS | PASS | 报告字节、退出状态、最终统计区段 |

共 13 个冻结 ELF × 5 个模拟器运行记录（65 条），对应 52 组基线比较。
包含十个原始示例、RVV/标量浮点/m5ops 兼容测试及两个原主操作码变异测试。
变异测试以旧基线实际行为为准，不宣称实现原生 X06/S05A 指令。
所有构建使用同一 ELF、输入和来宾输出路径，比较 simInsts、simOps、simTicks、system.cpu.numCycles；最终所选记录无差异。
原有示例中可观测的结果/状态随报告比较；额外完整状态覆盖由本版 checkpoint/storage 测试提供。

## 7. 与原生规范的差异

X06 使用实验 CUSTOM-0 (0x0b)，S05A 使用 CUSTOM-2 (0x5b)；类型完全由编码决定，不读 Md/Ad/amestype。
复用现有 32 个 M、4 个 Acc 及 AME 权限/所有权/dirty 状态；不是两个独立物理寄存器银行。
限定 AMENLEN=4、AMEUDSZ=32，其他形状触发非法指令；输出固定 4×4，INT8 深度16、半精度深度8。
X06 右矩阵按转置布局，半精度扩宽只取每行低四列；S05A 右矩阵行序，扩宽覆盖32元素并写相邻双M，md31非法。
固定 RNE、逐次 FP32 FMA、规范 NaN、AMEFFLAGS 累积，标量 fcsr 与 SoftFloat 环境保留；超界转整数采用本版显式契约。
没有增加完整原生 ISA、动态形状、原生 mtype、专用寄存器体系或新的 CPU/FU 时序模型。

## 8. 复现与已定位问题

详见 [测试入口说明](../../tests/ame_explicit_v1/README.md)。使用 `ame-gem5-rvv:local` 容器和仓库内工具链，仓库挂载到 `/work`。
工具版本、PDF/ELF/配置/模拟器/输入/预期输出/报告哈希见 evidence；完整二进制与 trace 保留在忽略跟踪的 results 目录。

开发期问题与最终证据的选择：

- 最初旧运行时的 512KiB 缓冲区不够；新测试独立使用二进制观测记录。
- 原有 Minor 的 semihost 功能读取可能赶在最后一个参数 store 排空前；测试运行时在 fence 后、semihost 前加入1024条 nop。此等待在被测内核之外，未修改模拟器或旧 example。
- 最初回归使用不同来宾输出路径且与链接重叠，记录不用于验收；最终回归固定相同路径并在二进制完成后执行。
- 字段审计最初错误期待 trace 文本 MatrixOp；实际显示为 Matrix。保留失败 JSON 和原 trace，修正解析后对同一 trace 重新检查。
- 所有时间戳原始运行、失败记录和故障注入证据均保留；最终采用记录列在 acceptance.json。

本轮完成研究性显式改造的正确性与兼容回归，不给出性能比较结论。后续性能实验需对齐右矩阵打包及扩宽工作量。
