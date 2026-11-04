# RVV 1.0 算子示例

本目录对应 `../example` 的 10 组算子，目标程序只使用标准
`rv64gcv` 指令。向量计算由 `<riscv_vector.h>` intrinsics 显式实现，
不需要 AME 编译器或 AME 指令。保留原示例的数据、Host C 参考实现和
报告格式（因此兼容性结构体、报告名称仍带 `ztt` 前缀）。

| 目录 | RVV 实现 |
| --- | --- |
| `gemm_fp32` | FP32 `C += A × B`，支持任意正整数 M/K/N 和 VL 尾部 |
| `gemm_int8` | INT8 输入、INT32 累加，附 INT32 → INT64 → INT32 转换 |
| `gemm_mixed` | 原示例的 INT8 输入、INT32 累加 |
| `gemm_mixed_source_types` | INT4/INT8/UINT4/UINT8、E4M3/E5M2 混合输入，转置、负乘积、饱和、舍入和浮点异常 |
| `gelu` | 原示例的 `x / (1 + 2^(-2x))` 近似 |
| `softmax` | 原示例的 base-2 Softmax，行最大值和有序求和 |
| `rmsnorm` | 平方、行归约、开方、倒数和归一化 |
| `rope` | 交错偶奇配对、向量 sin/cos 多项式、旋转 |
| `mha` | 两个 head 的 Q/K/V 投影、QKᵀ、Softmax 和 context |
| `ffn` | 两层矩阵乘法与上述 GELU 近似 |

## 编译和运行

使用支持 RVV 1.0 intrinsics 的 Clang 18+、LLD、llvm-objdump、Host C
编译器和 Python 3。目标程序使用本目录的 bare-metal semihosting runtime，
不依赖 RISC-V libc/libgcc。先在仓库根目录编译模拟器：

```sh
scons build/RISCV/gem5.opt -j16
make -C example_rvv1.0 test
```

单算子及参数：

```sh
make -C example_rvv1.0 gemm_fp32
make -C example_rvv1.0 build
make -C example_rvv1.0 test VLEN=128
make -C example_rvv1.0 test-vlens
make -C example_rvv1.0 test-tail
make -C example_rvv1.0 test CLANG=/path/to/clang LLVM_OBJDUMP=/path/to/llvm-objdump GEM5=/path/to/gem5.opt
```

`rvv_config.py` 使用本仓库的 `RiscvMinorCPU`、timing 内存和 full-system
semihosting。默认 VLEN=256、ELEN=64；可选 VLEN=128/256/512/1024。
所有向量循环由 `vsetvl` 返回值推进。每次测试重新运行 guest、清理旧报告，
并检查退出状态、运行时限、报告比较和反汇编。`RUN_TIMEOUT` 默认 180 秒，
`MAX_TICKS` 默认 10¹²，可在较慢机器上调整。

若主机编译工具较旧，可使用隔离环境。在仓库根目录执行：

```sh
docker build -t ame-gem5-rvv:local -f example_rvv1.0/Dockerfile example_rvv1.0
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" -w /work \
  ame-gem5-rvv:local scons build/RISCV/gem5.opt -j16
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" -w /work \
  ame-gem5-rvv:local make -C example_rvv1.0 test
```

Docker 内编译的 gem5 需要在同一镜像或兼容的系统中运行。

## 校验与输出

`make test` 将 MinorCPU 输出与独立 Host C 参考逐字节比较；
`gemm_fp32` 默认对照复制自原示例的 8×8 外部矩阵参考。
报告包含全输出的 FNV-1a 哈希及采样元素原始位模式，混合类型测试还逐项检查
全部输出、浮点 flags 和饱和标志。FP32 常规 GEMM 分开执行乘法和加法，
归约使用有序求和，避免改变原 Host 参考的舍入顺序。

```sh
# 默认配置矩阵对照 Host 参考
make -C example_rvv1.0/gemm_fp32 test-host-golden
# 原始 128×128 生成数据
make -C example_rvv1.0/gemm_fp32 test GOLDEN=host MATRIX_INPUT=
# 自定义 JSON：shape=[M,K,N]，a/b/c 为行优先数组
make -C example_rvv1.0/gemm_fp32 test GOLDEN=host MATRIX_INPUT=/path/to/input.json
```

`test-tail` 使用独立 Python FP32 参考和非整数输入检查 1×1×1、3×5×13、
5×7×19 矩阵，在 VLEN=128/256/512 下验证非方阵和尾部处理；另对两个
INT8 算子测试 13×13 矩阵，共 15 种组合。

每组的产物在 `<case>/build/`：`target/`、`host/`、`disasm/`、
`logs/`、`m5out/` 和 `reports/REPORT.md`。
汇总报告在 `build/reports/EXAMPLE_REPORT.md`。
`common/audit.py` 检查实际链接程序中的 RVV 指令，并拒绝 AME/未知指令。
`common/check_execution.py` 进一步检查 gem5 统计：实际提交的向量指令数
必须大于零，三个 AME Matrix 指令类别的提交数必须全部为零。

## 与原示例一致的范围

- GELU/Softmax/MHA/FFN 保持原示例的 base-2 数值定义；指数 helper
  按原 Host 实现截断为整数，并在指数小于 -126 时归零。
  这不是自然指数 Softmax 或完整 erf GELU 实现。
- RMSNorm 与原示例一样没有 epsilon 和可学习权重。
- RoPE 针对原示例 `[0,3]` 弧度角度域，以 FP64 向量多项式计算 sin/cos，
  舍入为 FP32 后旋转。它不是覆盖任意大角度的 libm 替代。
- 标准 RVV 1.0 没有 INT4/FP8 原生运算：混合类型先用软件打包、解码，
  核心乘加由 RVV 执行。整数饱和使用 `vsadd`/`vssub`；FP32 FMA 使用
  `frm` 的五种标准舍入模式，第六种 round-to-odd 在本测试数值域内通过
  精确 FP64 中间值和 `vfncvt.rod.f.f.w` 实现。flags 使用标准 `fflags`
  和 `vxsat`。
- 混合类型保留原前 14 组数值测试；原最后 3 组是 AME 专属的非法类型、
  M30/M31 寄存器跨度和 ACC 类型拒绝测试，没有 RVV 对应物，不计入本套测试。
- 本目录是正确性基线，尚未做缓存分块、展开和性能调优。

## 已执行的验证

2026-11-04，基于本仓库 `6677b2c8f6` 的 gem5 25.1.1.1-dev，使用
Ubuntu 24.04 容器和 Clang 18 构建，实际在 RiscvMinorCPU 上完成：

| 验证项 | 结果 |
| --- | --- |
| VLEN=128 / 256 / 512 的全部 10 组算子 | 30/30 PASS |
| FP32 非方阵与两个 INT8 算子的尾部组合 | 15/15 PASS |
| 原始 128×128 FP32 GEMM | PASS |
| 新旧目录 Host 参考输出比较 | 10/10 一致，混合类型比较保留的 14 组 |
| 实际执行指令统计 | 向量指令数 > 0，AME Matrix 指令数 = 0 |

共执行 46 次 guest 验证。各 VLEN 汇总在
`build/reports/VLEN128_REPORT.md`、`VLEN256_REPORT.md`、
`VLEN512_REPORT.md`；日志和机器可读摘要在 `build/validation/`。
这些文件是可重新生成的构建产物。
