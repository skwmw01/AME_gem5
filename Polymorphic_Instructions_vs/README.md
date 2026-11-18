# Ztt v0.6 动态指令开销实验

比较专用函数尾分派与共享函数体，测量的是两种软件组织方式；两者均使用多态 Ztt ISA。完整要求见 [experiment_plan.md](experiment_plan.md)。

```sh
cd Polymorphic_Instructions_vs
make all       # 汇编、bare-metal 驱动、反汇编和 ELF 符号表
make smoke     # R=1，七种序列，两方案各两次
make run       # 全部 R：196 个配置，18,816 次调用
make analyze   # 重新核验 build/full 并生成图表/报告
```

需要仓库 Ztt LLVM 工具链、`build/RISCV/gem5.opt` 和 Python 3.9+；绘图另需 matplotlib。运行脚本强制重建并记录源码、工具链、ELF、模拟器和轨迹哈希。现有结果目录不会被覆盖，可用 `python3 run.py --output build/another-run`。短测报告不能代替完整报告。

如果宿主 glibc/Python/HDF5 与现有 gem5 二进制不匹配，可先在宿主构建并保存环境，再在匹配运行库的本地容器中执行 `run.py --execute-prepared --simulate-only`，随后在宿主分析。本机已有 `ame-gem5-rvv:local` 镜像可提供运行库；仅使用镜像运行库，源码、ELF、模拟器和配置全部来自当前分支挂载目录，不使用镜像内的 RVV 测试或其他分支。容器无需 git 或 matplotlib。

本机复现命令（UID/GID 请按实际用户调整）：

```sh
# 从仓库根目录执行，完整实验
python3 Polymorphic_Instructions_vs/run.py --prepare-only
docker run --rm --network none --user 1015:1015 \
  -v "$PWD:/workspace" -w /workspace ame-gem5-rvv:local \
  python3 Polymorphic_Instructions_vs/run.py --execute-prepared --simulate-only
python3 Polymorphic_Instructions_vs/analyze.py Polymorphic_Instructions_vs/build/full
```

`run.py --gem5 PATH` 或 `AMEGEM5_GEM5` 可指定模拟器。Makefile 支持 `TOOLCHAIN`、`CLANG`、`OBJDUMP`、`LIBGCC` 覆盖，预装和源码构建两种 Ztt profile 均有分支。`config.py` 是现有 MinorCPU 平台的实验内快照，唯一行为改动是 workbegin/workend 控制整批 trace 开关，不改变时序参数。

`kernels.S` 中 `ins` 宏为每条指令附上分类 PC/大小；`li` 的实际展开条数从反汇编取得。两种测量包装的栈操作在区间外，区间内包含一个直接 `jal` 和内核 `ret`。驱动选择包装的函数指针发生在区间外，内核类型分派完全使用直接条件分支。

每次原始区间从起始 `rdinstret` 到结束 `rdinstret`（前闭后开）。分析器逐 PC 标记辅助指令，再把有效指令与 `instret` 差值对账。当前 MinorCPU 在 trace dump 之后才设置 CPSeq，且 CPSeq 是微操作序号，因此不把它当作架构提交计数。Exec 轨迹通过指令 flags 处理微操作；发现故障、缺失边界、未知 PC、错误输出或对账失败即拒绝生成成功报告。

驱动以固定种子 `0x6a09e667` 生成逻辑矩阵，测量前打包；宿主独立从逻辑行主序矩阵算参考。两方案共用同一 ELF 和输入/输出地址，分析器还比较实际矩阵内存访问序列的 SHA256。每次读取 AME 状态，逐元素比较 16 个原始输出位模式。

`results.bin` 为小端格式：8 个 uint64 头字段（magic、R 数、调用数、acquire 返回、AMEOWN、AMENLEN、AMEUDSZ、最终状态），随后每调用 88 字节（3 个 uint64：前后 instret、状态；16 个 uint32：输出位模式）。使用测量外的标准 semihosting 写二进制，避免公共运行时格式化文件 512 KiB 上限；分析器生成可读 CSV。

完整产物位于 `build/full/`：`REPORT.md`、`overhead.png/svg`、`validation.json`、`calls.csv`、`pairs.csv`、`summary.csv/json`、`pc_map.json`、`reference.json`、源码与环境快照，以及四个运行子目录的原始 trace/results/stats 和逐区间 `intervals.jsonl`。所有构建和运行产物均忽略版本跟踪。

分析器的故障回归检查可在仓库根目录执行 `python3 -m unittest discover -s Polymorphic_Instructions_vs -p test_analysis.py -v`，覆盖错误输出、截断文件、缺失边界、未知 PC、计数不符及微操作归并。

每次 `256R` 个有效 MAC；FP32/INT32 每轮四块，INT8 每轮一块。报告的准备比为 `(类型准备+其他准备)/mmulacc.2d`，内存搬运字节为 `128BR+64`，另列 64 字节累加器寄存器搬运。每次重新设类型，混合序列不表示跨调用类型缓存。
