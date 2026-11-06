#!/usr/bin/env python3
"""Plot verified AME/RVV measurements as standalone PNG and vector SVG figures."""
import argparse
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "example_rvv1.0/build/matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import Patch

from run import CASES

AME = "#2563B3"
RVV = "#148768"
INK = "#18283D"
MUTED = "#59687B"
GRID = "#DDE5EE"
LABELS = {
    "gemm_fp32": "gemm_fp32 · 128³",
    "gemm_int8": "gemm_int8 · 128³",
    "gemm_mixed": "gemm_mixed · 128³",
    "gemm_mixed_source_types": "gemm_mixed_source_types¹",
    "gemm_fp32_config": "gemm_fp32 · 8³（补充）",
}


def configure_fonts():
    for path in (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ):
        if Path(path).exists():
            font_manager.fontManager.addfont(path)
            family = font_manager.FontProperties(fname=path).get_name()
            break
    else:
        available = {font.name for font in font_manager.fontManager.ttflist}
        family = next((name for name in ("Noto Sans CJK SC", "Noto Sans CJK JP",
                                        "Microsoft YaHei", "SimHei")
                       if name in available), None)
        if not family:
            raise RuntimeError("A Chinese font is required; install fonts-noto-cjk.")
    plt.rcParams.update({
        "font.family": [family, "DejaVu Sans"],
        "font.size": 11,
        "text.color": INK,
        "axes.labelcolor": MUTED,
        "xtick.color": MUTED,
        "ytick.color": INK,
        "axes.unicode_minus": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.spines.bottom": False,
        "svg.fonttype": "path",
        "figure.facecolor": "#F7F9FC",
        "axes.facecolor": "#F7F9FC",
    })


def context(settings):
    vlen, matrix_lat, vector_lat, repeats = settings
    return (f"MinorCPU · 1 GHz · VLEN={vlen} · 无缓存 · {repeats} 轮中位数"
            f" · Matrix/Vector 延迟 {matrix_lat}/{vector_lat} cycles")


def save_figure(fig, directory, stem):
    for extension in ("png", "svg"):
        path = directory / f"{stem}.{extension}"
        fig.savefig(path, dpi=200,
                    facecolor=fig.get_facecolor(), metadata={"Creator": "AME/RVV benchmark/plot.py"})
        if extension == "svg":
            # Matplotlib emits trailing spaces in SVG path data.
            path.write_text("\n".join(line.rstrip() for line in
                                      path.read_text().splitlines()) + "\n")
    plt.close(fig)


def speedup_figure(pairs, settings, directory):
    fig = plt.figure(figsize=(13.6, 9.3))
    ax = fig.add_axes((0.30, 0.18, 0.66, 0.63))
    fig.text(0.055, 0.944, "逐算子相对加速比", fontsize=23, weight="bold")
    fig.text(0.055, 0.901, context(settings), fontsize=10.5, color=MUTED)
    positions = np.arange(len(CASES))
    ratios = [pairs[case]["rvv"]["cycles"] / pairs[case]["ame"]["cycles"]
              for case in CASES]
    values = np.log2(ratios)
    colors = [AME if ratio >= 1 else RVV for ratio in ratios]
    ax.axvspan(-3.4, 0, color=RVV, alpha=0.035)
    ax.axvspan(0, 4.1, color=AME, alpha=0.035)
    ax.barh(positions, values, height=0.53, color=colors, zorder=3)
    ax.scatter(values, positions, s=20, color=colors, zorder=4)
    for i, ratio in enumerate(ratios):
        winner, factor = ("AME", ratio) if ratio >= 1 else ("RVV", 1 / ratio)
        label = "持平" if math.isclose(ratio, 1, rel_tol=1e-12) else f"{winner} 加速 {factor:.3f}×"
        ax.text(values[i] + (0.09 if ratio >= 1 else -0.09), i, label,
                ha="left" if ratio >= 1 else "right", va="center",
                color=colors[i], fontsize=10.5, weight="bold")
    ax.axvline(0, color="#6E7D91", linewidth=1.1, zorder=2)
    ax.axhline(9.5, color=GRID, linestyle=(0, (3, 3)))
    ax.set_yticks(positions, [LABELS.get(case, case) for case in CASES], fontsize=10.5)
    ax.tick_params(axis="both", length=0, pad=10)
    ax.set_ylim(len(CASES) - 0.4, -0.65)
    ax.set_xlim(-3.4, 4.1)
    ax.set_xticks([-3, -2, -1, 0, 1, 2, 3],
                 ["RVV 8×", "RVV 4×", "RVV 2×", "持平", "AME 2×", "AME 4×", "AME 8×"],
                 fontsize=10)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_xlabel("横轴采用对数间距：每跨一格，加速比翻倍", labelpad=15, fontsize=10.5)
    ax.text(-1.7, -1.08, "← RVV 更快", ha="center", color=RVV, weight="bold")
    ax.text(1.7, -1.08, "AME 更快 →", ha="center", color=AME, weight="bold")
    fig.text(0.055, 0.073, "¹ 混合源类型一行是每轮 336 次 execute() 的累计耗时；虚线下方是原默认 8³ 补充案例。",
             fontsize=10, color=MUTED)
    fig.text(0.055, 0.037, "倍率 = 较慢实现的中位耗时 / 较快实现的中位耗时。实测配置、数值语义与编译器差异见 report.md。",
             fontsize=10, color=MUTED)
    save_figure(fig, directory, "ame_rvv_speedup")


def timing_panel(ax, pairs, cases, divisor, unit, title):
    positions = np.arange(len(cases))
    maximum = max(pairs[case][variant]["max_cycles"] / divisor
                  for case in cases for variant in ("ame", "rvv"))
    for variant, offset, color in (("ame", -0.18, AME), ("rvv", 0.18, RVV)):
        results = [pairs[case][variant] for case in cases]
        medians = np.array([result["cycles"] / divisor for result in results])
        lows = np.array([result["min_cycles"] / divisor for result in results])
        highs = np.array([result["max_cycles"] / divisor for result in results])
        ax.barh(positions + offset, medians, height=0.29, color=color, zorder=3)
        ax.errorbar(medians, positions + offset, xerr=[medians - lows, highs - medians],
                    fmt="none", ecolor=INK, elinewidth=0.9, capsize=2.4, zorder=4)
        for y, median, high in zip(positions + offset, medians, highs):
            ax.text(high + maximum * 0.015, y, f"{median:.3f}", va="center",
                    color=color, fontsize=10, weight="bold")
    ax.set_yticks(positions, [LABELS.get(case, case) for case in cases], fontsize=10.5)
    ax.set_ylim(len(cases) - 0.45, -0.65)
    ax.set_xlim(0, maximum * 1.24)
    ax.tick_params(axis="both", length=0, pad=10)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_title(title, loc="left", fontsize=13, weight="bold", pad=22)
    ax.set_xlabel(f"模拟耗时（{unit}） · 越短越快", labelpad=12, fontsize=10.5)


def timing_figure(pairs, settings, directory):
    fig, axes = plt.subplots(2, 1, figsize=(13.6, 11.8),
                             gridspec_kw={"height_ratios": [4, 7]})
    fig.subplots_adjust(left=0.30, right=0.95, top=0.82, bottom=0.145, hspace=0.47)
    fig.text(0.055, 0.95, "AME / RVV 实际模拟耗时", fontsize=23, weight="bold")
    fig.text(0.055, 0.914, context(settings), fontsize=10.5, color=MUTED)
    fig.legend(handles=[Patch(color=AME, label="AME"), Patch(color=RVV, label="RVV 1.0")],
               loc="upper left", bbox_to_anchor=(0.05, 0.898), ncol=2,
               frameon=False, fontsize=11)
    timing_panel(axes[0], pairs, CASES[:4], 1_000_000, "ms",
                 "A  大矩阵与混合类型套件 · 毫秒")
    timing_panel(axes[1], pairs, CASES[4:], 1_000, "μs",
                 "B  小算子与默认 FP32 案例 · 微秒")
    fig.text(0.055, 0.063, "柱长和数字表示中位数，黑色误差线表示各轮最小值至最大值；不表示置信区间。两幅子图的单位不同。",
             fontsize=10, color=MUTED)
    fig.text(0.055, 0.030, "¹ gemm_mixed_source_types 为每轮 336 次调用之和。1 GHz 下 1 cycle = 1 ns；这里只比较同一行的两种实现。",
             fontsize=10, color=MUTED)
    save_figure(fig, directory, "ame_rvv_latency")


def render_plots(pairs, settings, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    configure_fonts()
    speedup_figure(pairs, settings, directory)
    timing_figure(pairs, settings, directory)
    return directory


def main():
    # Import here so report.py can use render_plots without a circular import.
    from report import load_results

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=ROOT / "example_rvv1.0/build/performance/default")
    parser.add_argument("--output", type=Path, default=ROOT / "example_rvv1.0/figures")
    args = parser.parse_args()
    pairs, settings = load_results(args.input.resolve())
    render_plots(pairs, settings, args.output.resolve())
    print(f"[PASS] generated speedup/latency figures (PNG + SVG): {args.output}")


if __name__ == "__main__":
    main()
