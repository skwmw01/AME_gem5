#!/usr/bin/env python3
"""Validate measurements and generate the AME/RVV report, CSV and PNG/SVG charts."""
import argparse
import csv
import hashlib
import json
import os
import re
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from run import CASES, repository_head
from setup_toolchain import CHECKSUMS, COMMIT

ROOT = Path(__file__).resolve().parents[2]
SHAPES = {
    "gemm_fp32": "M=N=K=128，FP32",
    "gemm_int8": "128³，I8×I8→I32，含 I32→I64→I32",
    "gemm_mixed": "128³，I8×I8→I32",
    "gemm_mixed_source_types": "14 组数值测试，每轮 336 次 execute",
    "gelu": "4×4 FP32，原例 base-2 sigmoid 近似",
    "softmax": "4×4 FP32，逐行 base-2 Softmax",
    "rmsnorm": "4×4 FP32，逐行，无 epsilon/gamma",
    "rope": "4×4 FP32，角度 [0, 3] 弧度",
    "mha": "2 个 head，4×4 Q/K/V 与 attention",
    "ffn": "4×4，两次 GEMM + GELU",
    "gemm_fp32_config": "M=N=K=8，原配置文件默认输入",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_results(directory):
    results = json.loads((directory / "results.json").read_text())
    pairs = {}
    settings = set()
    fields = ("ticks", "instructions", "ops", "vector_instructions",
              "matrix_instructions", "loads", "stores")
    for result in results:
        case, variant = result["case"], result["variant"]
        if case not in CASES or variant not in ("ame", "rvv"):
            raise ValueError(f"unknown result: {case}/{variant}")
        if variant in pairs.setdefault(case, {}):
            raise ValueError(f"duplicate result: {case}/{variant}")
        if result.get("correct") is not True:
            raise ValueError(f"unsuccessful result: {case}/{variant}")
        out = directory / case / variant
        if json.loads((out / "result.json").read_text()) != result:
            raise ValueError(f"merged/per-case results differ: {out}")
        if digest(out / "target") != result["target_sha256"]:
            raise ValueError(f"binary digest differs: {out}")
        if digest(out / "guest.txt") != result["output_sha256"]:
            raise ValueError(f"guest digest differs: {out}")
        if (out / "guest.txt").read_bytes() != (out / "host.txt").read_bytes():
            raise ValueError(f"golden differs: {out}")
        roi = json.loads((out / "roi.json").read_text())
        expected = 336 if case == "gemm_mixed_source_types" else 1
        if result["roi_count_per_repeat"] != expected:
            raise ValueError(f"unexpected ROI count: {out}")
        if len(roi["regions"]) != expected * result["repeats"]:
            raise ValueError(f"incomplete ROI data: {out}")
        if roi["ticks_per_cycle"] != 1000 or roi["clock_hz"] != 1000000000:
            raise ValueError("this report expects the benchmark's 1 GHz clock")
        for key in ("vlen", "matrix_op_lat", "vector_op_lat"):
            if roi[key] != result[key]:
                raise ValueError(f"ROI/result setting differs: {out}/{key}")
        samples = []
        for repeat in range(result["repeats"]):
            regions = [r for r in roi["regions"] if r["repeat"] == repeat]
            if len(regions) != expected:
                raise ValueError(f"incomplete repetition: {out}/{repeat}")
            for region in regions:
                if region["ticks"] != region["end_tick"] - region["start_tick"]:
                    raise ValueError(f"invalid elapsed ticks: {out}/{repeat}")
            sample = {key: sum(r[key] for r in regions) for key in fields}
            sample["cycles"] = sample["ticks"] / roi["ticks_per_cycle"]
            if sample["cycles"] <= 0:
                raise ValueError(f"nonpositive cycles: {out}/{repeat}")
            if variant == "rvv" and (sample["matrix_instructions"] or
                                      sample["vector_instructions"] <= 0):
                raise ValueError(f"RVV ISA audit failed: {out}")
            if variant == "ame" and sample["matrix_instructions"] <= 0:
                raise ValueError(f"AME ISA audit failed: {out}")
            samples.append(sample)
        if samples != result["samples"]:
            raise ValueError(f"ROI and sample totals differ: {out}")
        cycles = [s["cycles"] for s in samples]
        for key, value in (("cycles", statistics.median(cycles)),
                           ("min_cycles", min(cycles)), ("max_cycles", max(cycles))):
            if result[key] != value:
                raise ValueError(f"incorrect summary statistic: {out}/{key}")
        settings.add(tuple(result[k] for k in
                           ("vlen", "matrix_op_lat", "vector_op_lat", "repeats")))
        pairs[case][variant] = result
    if set(pairs) != set(CASES) or len(settings) != 1:
        raise ValueError("full report requires all 11 workloads at identical settings")
    for case, pair in pairs.items():
        if set(pair) != {"ame", "rvv"}:
            raise ValueError(f"missing AME/RVV pair: {case}")
        if pair["ame"]["output_sha256"] != pair["rvv"]["output_sha256"]:
            raise ValueError(f"AME/RVV outputs differ: {case}")
    return pairs, settings.pop()


def comparison(pair):
    a, v = pair["ame"]["cycles"], pair["rvv"]["cycles"]
    speedup = a / v
    if speedup > 1:
        conclusion = f"RVV 加速 {speedup:.3f}×"
    elif speedup < 1:
        conclusion = f"AME 加速 {1 / speedup:.3f}×"
    else:
        conclusion = "持平"
    return a, v, speedup, (v / a - 1) * 100, conclusion


def table(pairs, cases):
    lines = ["| 算子 | AME cycles | RVV cycles | S=AME/RVV | RVV 耗时变化 | 结论 |",
             "|---|---:|---:|---:|---:|---|"]
    for case in cases:
        a, v, speedup, change, conclusion = comparison(pairs[case])
        lines.append(f"| `{case}` | {a:,.0f} | {v:,.0f} | {speedup:.4f} | "
                     f"{change:+.2f}% | {conclusion} |")
    return "\n".join(lines)


def relative(path, report):
    return Path(os.path.relpath(path, report.parent)).as_posix()


def gelu_diagnosis(pairs, directory, output):
    """Include compatible, complete follow-up experiments when available."""
    folder = directory.parent / "gelu_diagnosis"
    files = [folder / "results_original_filter.json", folder / "results.json"]
    if not all(path.is_file() for path in files):
        return ""
    original, cached = [json.loads(path.read_text()) for path in files]
    if len(original["results"]) != 5 or len(cached["results"]) != 8:
        return ""
    for study in (original, cached):
        if study["gem5_sha256"] != pairs["gelu"]["ame"]["files"].get("build/RISCV/gem5.opt"):
            return ""
        by_name = {row["name"]: row for row in study["results"]}
        for variant in ("ame", "rvv"):
            if by_name[variant + "_baseline"]["target_sha256"] != pairs["gelu"][variant]["target_sha256"]:
                return ""
        if any(not row["correct"] or row["output_sha256"] != pairs["gelu"]["ame"]["output_sha256"]
               for row in study["results"]):
            raise ValueError("GELU diagnostic output failed validation")
        if any(statistics.median(row["samples"]) != row["cycles"] for row in study["results"]):
            raise ValueError("incorrect GELU diagnostic median")
    a = {row["name"]: row for row in original["results"]}
    b = {row["name"]: row for row in cached["results"]}
    names = {
        "ame_baseline": "AME 原实现，无 I-cache",
        "ame_no_sqrt": "AME 直接使用 2，开方替换为 NOP",
        "ame_matrix6": "AME Matrix 延迟/发射间隔改为 6",
        "ame_matrix1": "AME Matrix 延迟/发射间隔改为 1",
        "rvv_baseline": "RVV 原实现，无 I-cache",
        "ame_icache": "AME 原实现，增加 I-cache",
        "rvv_icache": "RVV 原实现，增加 I-cache",
        "ame_icache_matrix6": "AME 有 I-cache，Matrix 延迟/发射间隔改为 6",
    }
    def rows(study):
        lines = ["| 实验 | 三轮 cycles | 中位 cycles | 强制重定向次数/轮 |",
                 "|---|---|---:|---:|"]
        for row in study["results"]:
            values = " / ".join(f"{value:,.0f}" for value in row["samples"])
            redirects = statistics.median(t["forced_redirects"] for t in row["trace"])
            lines.append(f"| {names[row['name']]} | {values} | {row['cycles']:,.0f} | {redirects:.0f} |")
        return "\n".join(lines)
    base, no_sqrt = a["ame_baseline"]["cycles"], a["ame_no_sqrt"]["cycles"]
    gap_before = b["ame_baseline"]["cycles"] - b["rvv_baseline"]["cycles"]
    gap_after = b["ame_icache"]["cycles"] - b["rvv_icache"]["cycles"]
    ame_fetches = statistics.median(t["fetch_requests"] for t in a["ame_baseline"]["trace"])
    rvv_fetches = statistics.median(t["fetch_requests"] for t in a["rvv_baseline"]["trace"])
    link = relative(folder, output)
    script = relative(Path(__file__).parent / "diagnose_gelu.py", output)
    return f"""### 6.2 GELU 的主要差距来源：补充对照实验

后续针对“RVV 更快是否主要因为省掉 sqrt(4)”进行了实测。
**证据指向当前 AME 模型的频繁串行化与无指令缓存取指之间的相互影响。**
只删除常量开方的影响较小；在无缓存配置中，Matrix 功能单元的标称延迟也没有决定这里的总耗时。
此前仅依据代码强调常量简化、指数实现和功能单元延迟，不足以说明主要因素，以下对照提供进一步依据。

第一组保留主报告的原始总线/SnoopFilter 配置，各实验使用同一路径启动保存的 ELF，
保持代码地址、输入准备和测量边界。删除开方的实验只修改三个 32 位机器字：把常量 4 改为 2、
把 `msqrt.ew` 替换为同长度 NOP、让后续乘法读取全 2 矩阵。
未删除额外缓冲区和类型设置，避免把多项优化合并为“少一次开方”。

{rows(original)}

AME 从 {base:.0f} 降到 {no_sqrt:.0f} cycles，仅减少 {base - no_sqrt:.0f} cycles（{100 * (base - no_sqrt) / base:.2f}%）。
这个差值包含少一次串行化的影响，不能全部计为平方根算术延迟。
Matrix 的 opLat/issueLat 从 16 降到 6 或 1，三轮耗时均未改变，说明在这一配置下它们的开销被其他等待遮蔽。

ROI 的 Branch/Fetch 日志确认，AME 每轮发生 **23 次强制取指重定向**，RVV 为 **0 次**。
ROI 内 CPU 取指请求数的中位数分别为 **{ame_fetches:.0f} 次与 {rvv_fetches:.0f} 次**，
尽管已提交指令数分别只有 29 条与 57 条。
这些重定向来自 `SerializeAfter` 等标记，不应当全部解释为分支预测失败。
AME 的类型配置、算术和访存操作具有串行化标记；MinorCPU 在提交后改变取指流，重新取得后续指令。
无 I-cache 时，频繁重新取指需要经过总线和 DRAM，短算子因此积累了大量非算术等待。
这是当前 gem5 的实现方式，不能视为真实 AME 硬件必然具有的开销。

第二组固定相同 ELF 和数据访存路径，仅对照是否增加 **32 KiB、2 路、tag/data/response 延迟均为 1 cycle 的 I-cache**。
本仓库的 I-cache 与直连 CPU 数据端口组合会触发 SnoopFilter 断言，因此第二组的所有实验都统一关闭可选 SnoopFilter，
保留一致性广播，D-cache 仍然关闭。此组应使用自己的无缓存基线，不能直接与第一组相减。

{rows(cached)}

在第二组内部，增加指令缓存后，AME/RVV 的绝对周期差从 **{gap_before:.0f} 缩小到 {gap_after:.0f} cycles**，
减少约 **{100 * (1 - gap_after / gap_before):.1f}%**，而 AME 的 23 次串行化重定向仍然存在。
有 I-cache 后再将 Matrix 延迟由 16 改为 6，AME 从 {b['ame_icache']['cycles']:.0f} 降到
{b['ame_icache_matrix6']['cycles']:.0f} cycles；此时功能单元延迟的影响才清楚显现。

这些实验支持“串行化叠加取指等待是当前配置中的主要差距来源”，不构成各项开销可独立相加的精确分解。
缓存还会改变总线竞争和进入 ROI 时的状态；常量设置、指数实现和编译器差异仍然存在。
主报告原有性能表和图保持原始配置的数据，未被本节的诊断配置覆盖。

共新增 13 个对照配置、39 轮，全部输出报告与原 Host golden 一致。
原始配置结果：[results_original_filter.json]({link}/results_original_filter.json)；
缓存对照：[results.json]({link}/results.json)；每项的 `m5out/trace.txt` 保留 ROI 内 Branch/Fetch 跟踪。
诊断脚本：[diagnose_gelu.py]({script})。复现命令如下，使用已有完整性能测试产物：

```bash
docker run --rm --user "$(id -u):$(id -g)" \\
  -v "$PWD:/work" -w /work ame-gem5-rvv:local \\
  python3 example_rvv1.0/benchmark/diagnose_gelu.py --original-filter-controls

docker run --rm --user "$(id -u):$(id -g)" \\
  -v "$PWD:/work" -w /work ame-gem5-rvv:local \\
  python3 example_rvv1.0/benchmark/diagnose_gelu.py
```

随后重新运行 `report.py`，会自动纳入与主报告 ELF 匹配的完整诊断结果。

"""


def make_report(pairs, settings, directory, output):
    vlen, matrix_lat, vector_lat, repeats = settings
    env_path = directory / "environment.json"
    env = json.loads(env_path.read_text()) if env_path.exists() else {}
    os_name = next((line.split("=", 1)[1].strip('"')
                    for line in env.get("os", "").splitlines()
                    if line.startswith("PRETTY_NAME=")), "未记录（见 Dockerfile）")
    baseline = env.get("git_head") or repository_head()
    timestamp = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    a0, v0 = pairs["gemm_fp32"]["ame"], pairs["gemm_fp32"]["rvv"]
    log = (directory / "gemm_fp32/ame/simulation.log").read_text()
    version = re.search(r"^gem5 version (.+)$", log, re.MULTILINE)
    version = version.group(1) if version else "见 simulation.log"
    binary_hashes = {r["files"].get("build/RISCV/gem5.opt")
                     for pair in pairs.values() for r in pair.values()}
    gem5_hash = next(iter(binary_hashes)) if len(binary_hashes) == 1 else None
    data_link = relative(directory, output)
    code_link = relative(Path(__file__).parent, output)
    figures_link = relative(output.parent / "figures", output)
    workload_count = len(CASES) * 2 * repeats
    roi_count = sum(r["roi_count_per_repeat"] * repeats
                    for pair in pairs.values() for r in pair.values())
    wins = [case for case in CASES[:-1] if comparison(pairs[case])[2] > 1]
    losses = [case for case in CASES[:-1] if comparison(pairs[case])[2] < 1]
    summary = "；".join(f"`{case}`：{comparison(pairs[case])[4]}"
                       for case in ("gelu", "gemm_fp32", "mha"))
    scopes = "\n".join(f"| `{case}` | {SHAPES[case]} |" for case in CASES)
    samples = ["| 算子 | AME 各轮 cycles（执行顺序） | AME min–max | RVV 各轮 cycles（执行顺序） | RVV min–max |",
               "|---|---|---|---|---|"]
    instructions = ["| 算子 | AME 总指令 | AME Matrix 类 | AME 辅助 RVV | RVV 总指令 | RVV 向量指令 |",
                    "|---|---:|---:|---:|---:|---:|"]
    hashes = ["| 算子 | AME/RVV/Host 一致的输出 SHA256 |", "|---|---|"]
    for case in CASES:
        a, v = pairs[case]["ame"], pairs[case]["rvv"]
        sample_text = lambda r: " / ".join(f"{s['cycles']:,.0f}" for s in r["samples"])
        samples.append(f"| `{case}` | {sample_text(a)} | {a['min_cycles']:,.0f}–{a['max_cycles']:,.0f} | "
                       f"{sample_text(v)} | {v['min_cycles']:,.0f}–{v['max_cycles']:,.0f} |")
        count = lambda r, k: statistics.median(s[k] for s in r["samples"])
        instructions.append(f"| `{case}` | {count(a, 'instructions'):,.0f} | "
                            f"{count(a, 'matrix_instructions'):,.0f} | {count(a, 'vector_instructions'):,.0f} | "
                            f"{count(v, 'instructions'):,.0f} | {count(v, 'vector_instructions'):,.0f} |")
        hashes.append(f"| `{case}` | `{a['output_sha256']}` |")
    verdict = lambda case: comparison(pairs[case])[4]
    diagnosis = gelu_diagnosis(pairs, directory, output) if settings == (256, 16, 6, 3) else ""
    gelu_note = (
        "后续对照实验表明，原配置下主要差距来自 AME 串行化与无缓存取指的相互影响，"
        "省去常量开方只带来较小收益；具体数据见后面的 GELU 补充实验。"
        if diagnosis else
        "AME 路径的类型配置、常量加载和串行化会影响这个小算子的耗时；"
        "各因素的主次需要额外的对照实验确认。"
    )
    return f"""# AME 与 RVV 1.0 算子性能对比报告

报告生成时间：{timestamp}（Asia/Shanghai）。源代码基线：`{baseline}`；
各次构建的输入文件散列另存于 `result.json`。本报告由 [benchmark/report.py]({code_link}/report.py)
读取实际模拟结果生成，没有使用估算时间代替实测。

## 1. 结论与性能对比

在下述固定配置下，10 个原算子中 RVV 快于 AME 的有 **{len(wins)} 个**，慢于 AME 的有 **{len(losses)} 个**。
{summary}。此外单独测量原 FP32 配置文件的 8×8 输入，避免把 128×128 数据与原默认小矩阵混为一谈。

**统一口径：S = AME 中位耗时 / RVV 中位耗时。** S > 1 表示 RVV 加速 S 倍；S < 1 表示
AME 相对 RVV 加速 1/S 倍，即 RVV 耗时是 AME 的 1/S 倍。耗时变化 = (RVV/AME − 1) × 100%。
下表使用 {repeats} 轮的中位数，单位是模拟 CPU 周期，不是宿主机运行秒数。
CPU 为 1 GHz，故 **1 cycle = 1 ns，时间 μs = cycles / 1000**。

### 1.1 直观对比图

**相对加速比：蓝色表示 AME 更快，绿色表示 RVV 更快；中心线表示持平。**
图中逐项标注“AME 加速 X×”或“RVV 加速 X×”，横轴采用对数间距，每跨一格倍率翻倍。
这与下表 S=AME/RVV 的原始比值口径不同：图中文字始终给出较快一方相对较慢一方的加速倍数。

![AME 与 RVV 逐算子相对加速比]({figures_link}/ame_rvv_speedup.png)

**绝对耗时：同一行中柱子越短越快。** 大矩阵使用 ms，小算子使用 μs，分面避免小算子被数量级差异淹没。
柱子为中位数，误差线为最小值至最大值；两幅子图不可直接比较柱长。

![AME 与 RVV 模拟耗时对比]({figures_link}/ame_rvv_latency.png)

可用于缩放或导出的矢量原图：[加速比 SVG]({figures_link}/ame_rvv_speedup.svg)、
[耗时 SVG]({figures_link}/ame_rvv_latency.svg)。图表直接读取同一份实测数据，不重新运行模拟器。

### 1.2 逐算子主表

{table(pairs, CASES[:-1])}

### 1.3 原 FP32 默认配置补充

{table(pairs, ("gemm_fp32_config",))}

`gemm_mixed_source_types` 一行是每轮 336 次 `execute()` 的 ROI 耗时之和，不是一次矩阵乘法。
各行工作量不同，不将它们相加或取平均倍率来代表整体模型吞吐率。

## 2. 对比范围与正确性

AME 输入来自 `example/`，RVV 输入来自 `example_rvv1.0/`，保留各自现有算子实现。
脚本只在构建目录生成插桩副本，不修改原算子源码。相同算子采用相同输入、输出格式和数学语义。

| 算子 | 实测工作负载 |
|---|---|
{scopes}

GELU 沿用原示例的 `x / (1 + 2^(-2x))` 近似；Softmax 沿用 base-2 指数。
RVV 的指数辅助函数按原输入域构造整数指数值，不能把这里的结果外推为任意实数输入上的通用 GELU/Softmax 性能。
RoPE 的 RVV 实现以 FP64 的 14 项 Taylor 展开计算正余弦后转回 FP32，仅覆盖原例的角度域。

混合源类型目录原有 17 组，RVV 对应其中 **14 组数值测试**。AME 插桩副本也只运行这 14 组，
保留类型组合、转置/取负、舍入、饱和和异常标志等数值检查，排除最后 3 组 AME 专属的非法类型/寄存器跨度检查。
每轮有 336 次 `execute()`，两边数量一致。

本次共验证 **22 个目标二进制、{workload_count} 轮工作负载、{roi_count} 段 ROI**：

- 每个目标程序的完整输出报告逐字节等于独立编译运行的 Host 标量参考报告。
  普通算子报告包含全输出 FNV-1a 哈希及采样元素原始位模式；混合类型报告逐项包含全部数值和状态标志。
- 同一程序各轮输出哈希一致；AME 与 RVV 的完整输出报告也逐字节一致。
- 所有 RVV ROI 都实际提交了向量指令，Matrix 类计数均为 0；所有 AME ROI 的 Matrix 类计数均大于 0。
- `report.py` 再次检查二进制/输出散列、Host 输出、ROI 完整性、逐轮统计和中位数后才生成此文档。

这证明本报告列出的输入通过验证；不等同于穷举验证任意输入。

## 3. 模拟器与编译环境

| 项目 | 本次配置 |
|---|---|
| 执行容器 | `ame-gem5-rvv:local`，{os_name} |
| Python | {env.get('python', '见 environment.json')} |
| Host 标量编译器 | {env.get('host_cc', '见 build-host.log')} |
| gem5 | `{version}`，仓库 `build/RISCV/gem5.opt` |
| CPU | 单核 `RiscvMinorCPU`，timing 模式，1 GHz |
| 运行方式 | 全系统裸机 ELF + RISC-V semihosting，无 guest OS |
| RVV | VLEN={vlen} bits，ELEN=64 bits |
| 向量非访存 FU | opLat={vector_lat} cycles，issueLat=1 cycle |
| AME Matrix FU | opLat={matrix_lat} cycles，issueLat={matrix_lat} cycles |
| AME tile | 原示例 4×4 square；INT8 K 步长 16 |
| 内存 | 128 MiB，`DDR3_1600_8x8`，`SystemXBar` |
| 缓存 | 无 I-cache/D-cache；CPU 指令/数据端口直接连接 SystemXBar |
| cache_line_size 参数 | 64 bytes（不代表配置了 cache） |
| AME 编译器 | {a0['compiler'].splitlines()[0]} |
| RVV 编译器 | {v0['compiler'].splitlines()[0]} |
| 链接器 | {env.get('lld', 'LLD 18，见 build-target.log')}，两边一致 |
| AME ISA 编译参数 | `-march=rv64gcv_xxiangshanztt -mabi=lp64d` |
| RVV ISA 编译参数 | `-march=rv64gcv -mabi=lp64d` |
| 共同优化参数 | `-O2 -ffp-contract=off -fno-vectorize -fno-slp-vectorize` |
| 共同裸机参数 | `-ffreestanding -fno-builtin -mcmodel=medany -nostdlib -static` |
| 启动和运行时 | 两边共用 `example/common/crt0.S`、`runtime.c`、`link.ld` |
| 重复测量 | 每个二进制在同一 guest 内运行 {repeats} 轮；每轮重置统计 |
| 仿真限制 | 每个程序最多 30,000,000,000,000 ticks，默认宿主超时 1800 秒 |

AME 工具链固定到 `OpenXiangShan/AME_llvm` 子模块提交 `{COMMIT}` 中的预编译归档。
安装脚本通过 GitHub Blob API 获取两个固定 blob，验证分片和完整包 SHA256 后解压。
完整包 SHA256：`{CHECKSUMS['ame_toolchain.tar.gz']}`。
gem5 二进制 SHA256：`{gem5_hash or '请查各 result.json 的 files 字段'}`。

**编译器版本不相同**：AME 需要仓库配套 Clang 21 扩展工具链，标准 RVV intrinsics 使用 Clang 18。
因此这里比较的是“当前实现 + 对应编译器 + 当前 gem5 模型”的实际执行结果，不是剥离编译器影响的纯 ISA 实验。
`-fno-vectorize/-fno-slp-vectorize` 不会禁止编译器在内存清零/复制等辅助代码中生成 RVV；
AME 路径中的此类向量指令计数在第 5 节单独列出。

## 4. 测量边界与统计方法

测量标记是 gem5 的 `m5_work_begin/end` 指令编码，并用 `fence rw,rw` 约束访存。
模拟器遇到 begin 后重置 CPU 统计，遇到 end 记录实际经过的 ticks 和已提交指令计数。
周期数按 `(end_tick − start_tick) / 1000` 计算，包含取指、访存和流水线等待，
不使用可能排除空闲阶段的 CPU 活跃周期计数代替总耗时。

普通算子在输入初始化完成后进入 ROI，输出描述、哈希、文本格式化和 semihost 文件输出位于 ROI 外。
ROI 包含真实算子调用、GEMM 分块/打包，以及 AME acquire、类型配置和 release；
RoPE 的 ROI 放在实际 tile 计算函数内。MHA/FFN 计量整条算子组合路径。

混合源类型套件逐次包围 `execute()`：包括 AME 输入打包、类型/状态设置、矩阵计算、结果复制，
或 RVV 软件解码、舍入/饱和处理及向量计算；输入场景构造、结果登记、报告输出和套件级 acquire/release 在外。
将每轮 336 段耗时求和后再对 {repeats} 轮取中位数。边界指令和 fence 的开销没有额外扣除，
该行与单个连续 ROI 的微内核不是同一测量粒度。

没有另外丢弃首轮作为预热。轮间重新准备输入并重置统计，但不重置 CPU、分支预测器或 DRAM 状态；
初始化虽然不计时，仍会影响进入 ROI 时的硬件状态。以下保留所有样本及范围，短算子的相对波动更明显。
这些重复是在同一仿真进程中取得的，不构成独立样本置信区间。
更换构建目录、二进制布局或启动参数也可能改变进入 ROI 前的状态；复测应保留完整命令与配置，不能要求每轮周期完全相同。

{'\n'.join(samples)}

## 5. 指令计数佐证

表中使用每轮计数的中位数。Matrix 类是 gem5 `Matrix + MatrixMov + MatrixOP` 分类之和，
**不包括所有 AME 设置/加载/存储指令**。总指令是 `commitStats0.numInsts`，
向量计数是 `numVecInsts`；微操作另存为 `ops`。这些分类计数不能直接等同为算术运算次数或内存字节数。

{'\n'.join(instructions)}

AME 路径可能含辅助 RVV，RVV 路径的 Matrix 类计数全部为 0。
统计支持对实现工作量的比较，但不足以单独证明某个瓶颈来自 DRAM 带宽、依赖链或功能单元。

## 6. 逐算子分析

1. **FP32 GEMM：{verdict('gemm_fp32')}。** 128³ 下两边接近；AME 的 tile 复制/打包也在计时内，
   RVV 沿输出列向量化并直接读取矩阵，保留逐项 FP32 乘法和加法。
   AME 的矩阵算术粒度更大，却还有大量标量/辅助向量指令及访存开销，不能仅按矩阵指令条数预测总耗时。
   原默认 8³ 的结论是 {verdict('gemm_fp32_config')}，说明尺寸变化会改变相对开销。
2. **INT8 GEMM：{verdict('gemm_int8')}。** AME 每个 K 步长为 16，将 4 个 4×4 square 打包；
   RVV 按 K 循环加载字节、符号扩展到 I32 并做向量 MAC，提交的向量运算数量更高。
   两边均保留原例额外的 I32→I64→I32 转换，所以此行不只是裸 INT8 GEMM。
3. **Mixed GEMM：{verdict('gemm_mixed')}。** 此目录实际是 I8×I8→I32，去掉上面的往返转换。
   当前 RVV `gemm_int8` 反而比 `gemm_mixed` 用时短，不能解释为“加转换会加速”。
   两者共用 RVV GEMM 内核但二进制/数据布局不同；无缓存取指、DRAM 状态和布局可能影响结果，
   这是待进一步拆分验证的解释，不是已证实的单一瓶颈。
4. **Mixed source types：{verdict('gemm_mixed_source_types')}。** AME 硬件路径支持混合输入格式，
   RVV 还需软件执行 INT4/FP8 等格式解码、状态/舍入处理。整行包含 336 次调用的这些成本。
   它更适合评价当前混合类型实现与测试集合，不应当成一个固定尺寸 GEMM 的吞吐指标。
5. **GELU：{verdict('gelu')}。** 原输入允许 RVV 通过整数指数位构造实现 base-2 指数，
   16 个元素在少量向量批次内完成。{gelu_note}
   本结论限于当前近似函数、输入域和模拟器配置。
6. **Softmax：{verdict('softmax')}。** AME 有矩阵逐行归约和广播操作；RVV 显式循环各行，
   分别求最大值、指数、按序求和及归一化。保持原求和顺序也限制了可采用的重排。
7. **RMSNorm：{verdict('rmsnorm')}。** 与 Softmax 类似，RVV 的逐行有序归约、标量倒数和
   多次向量设置增加了小尺寸开销；本例没有常见生产实现中的 epsilon 或 gamma 乘法。
8. **RoPE：{verdict('rope')}。** AME 用原生 sin/cos 矩阵指令，受当前 Matrix FU 延迟模型约束；
   RVV 则显式计算 14 项 FP64 多项式再转换为 FP32。该结果同时体现数学实现与功能单元建模差异，
   不代表真实硬件的 sin/cos 一定能以同样成本完成。
9. **MHA：{verdict('mha')}。** 原例为两个 head 的小矩阵组合，包含 Q/K/V 投影、QKᵀ、
   Softmax 和 context。AME 按矩阵粒度完成，RVV 多次进入逐行/逐 K 循环，提交指令更多。
   这里没有测试生产 Transformer 的大 sequence、batch 或 head dimension。
10. **FFN：{verdict('ffn')}。** 两次小 GEMM 和 GELU 串联；GELU 单项的 RVV 优势未抵消
    整体矩阵乘法和调用开销。单独优化一个子算子不等于整条计算路径同比加速。

### 6.1 结论边界与后续优化方向

无缓存配置使取指和数据访问直接进入内存系统；两套编译器、布局、输入规模和功能单元延迟都会影响倍率。
RVV 当前实现以正确复现原例为目标，尚未进行多行寄存器分块、B 向量复用等 GEMM 调优。
可先尝试这些优化并继续逐字节校验；若改为融合乘加或重排浮点归约，需单独定义并验证数值误差契约。

增加缓存、更换 VLEN、改变 Matrix/Vector FU 延迟、扩大 MHA/FFN 尺寸都值得另做实验。
本报告只包含上述一套配置的实测，未对这些未测配置作性能承诺，也未将模拟周期解释为真实芯片结果。

{diagnosis}## 7. 脚本与复现步骤

| 文件 | 用途 |
|---|---|
| [setup_toolchain.py]({code_link}/setup_toolchain.py) | 下载并校验固定 AME Clang 归档；支持离线归档 |
| [run.py]({code_link}/run.py) | 生成插桩副本、编译 Host/目标、并行仿真、正确性/ISA 检查、汇总 JSON |
| [perf_config.py]({code_link}/perf_config.py) | AME/RVV 共用系统配置与 ROI 事件采集 |
| [roi.h]({code_link}/roi.h) | 工作区间标记及访存 fence |
| [report.py]({code_link}/report.py) | 复核完整结果，生成本文、CSV 与对比图 |
| [plot.py]({code_link}/plot.py) | 使用 Matplotlib 绘制加速比/耗时图，输出 PNG 和 SVG |
| [Dockerfile](Dockerfile) | Ubuntu 24.04、Clang/LLD 18、gem5 构建依赖与中文绘图环境 |

以下命令在仓库根目录执行。需要 Docker；首次构建镜像/下载工具链需要网络。
Dockerfile 使用发行版包仓库，重建时补丁版本可能变化；本文记录的是实际测量版本。
宿主机速度只影响仿真完成时间，不参与性能倍率。`--jobs` 是宿主侧并行仿真数，不是 guest 核数。

### 7.1 首次准备环境

```bash
cd /data/mingwei/project/xiangshanwmw/AME_gem5

docker build -t ame-gem5-rvv:local \\
  -f example_rvv1.0/Dockerfile example_rvv1.0

docker run --rm --user "$(id -u):$(id -g)" \\
  -v "$PWD:/work" -w /work ame-gem5-rvv:local \\
  scons build/RISCV/gem5.opt -j16 --ignore-style

docker run --rm --user "$(id -u):$(id -g)" \\
  -v "$PWD:/work" -w /work ame-gem5-rvv:local \\
  python3 example_rvv1.0/benchmark/setup_toolchain.py --direct
```

已有 gem5 和工具链时可跳过相应编译/安装步骤。新增绘图依赖为 `python3-matplotlib` 和 `fonts-noto-cjk`，
旧版镜像需要先重新执行上面的 `docker build`，之后从 7.2 开始。
内存不足时将 SCons 的 `-j16` 调低。`--direct` 忽略代理环境变量；需要代理时移除此选项并配置容器网络。
离线时将校验一致的完整归档放到仓库内，再用 `--archive /work/路径/ame_toolchain.tar.gz`。
安装器拒绝覆盖已有非空且未标记为同一归档的工具链目录；可以 `--dest` 安装到新目录，
再给 `run.py` 指定相应 `--ame-clang` 与 `--objdump`。

### 7.2 重新测量全部算子并生成报告

```bash
docker run --rm --user "$(id -u):$(id -g)" \\
  -v "$PWD:/work" -w /work ame-gem5-rvv:local \\
  python3 example_rvv1.0/benchmark/run.py \\
    --jobs 4 --repeats {repeats} --vlen {vlen} \\
    --matrix-op-lat {matrix_lat} --vector-op-lat {vector_lat} \\
    --output example_rvv1.0/build/performance/default

docker run --rm --user "$(id -u):$(id -g)" \\
  -v "$PWD:/work" -w /work ame-gem5-rvv:local \\
  python3 example_rvv1.0/benchmark/report.py \\
    --input example_rvv1.0/build/performance/default \\
    --output example_rvv1.0/report.md
```

默认运行 10 个算子和额外的 8³ FP32 案例，每种 AME/RVV 各测 {repeats} 轮。
正常结束打印 `[PASS] 22 measured binaries`，随后报告脚本打印生成路径。
`report.py` 同时在报告旁的 `figures/` 中生成两张图的 PNG 和 SVG，无须额外执行绘图命令。
如果只更新图表，可运行 `python3 example_rvv1.0/benchmark/plot.py`；默认读取已有结果，不再仿真。
直接在宿主执行绘图需 Python 3.12+、Matplotlib、NumPy 和中文字体（推荐 Noto Sans CJK）。
`--resume` 可复用指纹匹配且产物校验通过的成功结果；需要新一轮实测时不要传它。
默认目录中的同名产物会更新；要保留旧结果，请使用新的 `--output` 目录。

### 7.3 单独复测与参数设置

```bash
# 两个算子的快速对比；仍会校验 Host 与 AME/RVV 输出。
docker run --rm --user "$(id -u):$(id -g)" \\
  -v "$PWD:/work" -w /work ame-gem5-rvv:local \\
  python3 example_rvv1.0/benchmark/run.py \\
    --cases gelu rope --repeats 3 --jobs 2 \\
    --output example_rvv1.0/build/performance/quick

# 查看全部可配置项。
docker run --rm --user "$(id -u):$(id -g)" \\
  -v "$PWD:/work" -w /work ame-gem5-rvv:local \\
  python3 example_rvv1.0/benchmark/run.py --help
```

可用 `--variants ame` 或 `--variants rvv` 单独运行一侧；`--vlen` 支持 128/256/512/1024，
`--matrix-op-lat`、`--vector-op-lat` 调整模型延迟。改变配置应使用新目录并同时测量两侧。
完整 `report.py` 要求 11 对工作负载齐全且配置一致；局部运行请直接查看其 `results.json`，
不能以不完整数据覆盖全套报告。若分开运行两侧，最后以默认双侧 `run.py --resume` 合并并交叉校验。

不使用 Docker 时需准备兼容 gem5 二进制的 Linux 用户态、Python 3.12+、Clang/LLD 18、Host C 编译器和
已安装的 AME 工具链；可通过 `--gem5 --ame-clang --rvv-clang --objdump --linker --host-cc` 指定路径。
本次宿主旧系统不直接运行 Ubuntu 24.04 内构建的 gem5，统一在容器中执行。

## 8. 原始产物与审计入口

当前数据目录：[build/performance/default]({data_link}/)。构建产物在 Git 忽略目录内；
重新克隆时需要运行脚本生成，本文中的样本、倍率和输出散列保留了此次结果。

- [`results.json`]({data_link}/results.json)：22 个结果的输入散列、编译器、样本、中位数和输出散列。
- [`comparison.csv`]({data_link}/comparison.csv)：与性能主表一致的机器可读数据（含默认 8³ 补充案例）。
- [`environment.json`]({data_link}/environment.json)：运行环境版本。
- `<case>/<ame|rvv>/roi.json`：每段 begin/end ticks、指令分类和工作轮次。
- 同目录 `host.txt` / `guest.txt`：逐字节核对的参考/目标完整输出。
- 同目录 `build-target.log`、`build-host.log`、`simulation.log`、`disassembly.txt`：完整命令和运行证据。
- 同目录 `m5out/config.json` / `config.ini`：实际实例化的 gem5 配置。

以下为完整输出报告的 SHA256；同一行 AME、RVV 及各自 Host 均相同。

{'\n'.join(hashes)}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=ROOT / "example_rvv1.0/build/performance/default")
    parser.add_argument("--output", type=Path, default=ROOT / "example_rvv1.0/report.md")
    parser.add_argument("--csv", type=Path, help="default: INPUT/comparison.csv")
    args = parser.parse_args()
    directory, output = args.input.resolve(), args.output.resolve()
    pairs, settings = load_results(directory)
    from plot import render_plots
    render_plots(pairs, settings, output.parent / "figures")
    report = make_report(pairs, settings, directory, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report)
    csv_path = args.csv or directory / "comparison.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("case", "ame_cycles", "rvv_cycles", "ame_over_rvv_speedup",
                         "rvv_time_change_percent", "conclusion", "ame_min_cycles",
                         "ame_max_cycles", "rvv_min_cycles", "rvv_max_cycles"))
        for case in CASES:
            pair = pairs[case]
            writer.writerow((case, *comparison(pair), pair["ame"]["min_cycles"],
                             pair["ame"]["max_cycles"], pair["rvv"]["min_cycles"],
                             pair["rvv"]["max_cycles"]))
    print(f"[PASS] verified 22 binaries and all ROI samples; report: {output}; "
          f"CSV: {csv_path}; PNG/SVG charts: {output.parent / 'figures'}")


if __name__ == "__main__":
    main()
