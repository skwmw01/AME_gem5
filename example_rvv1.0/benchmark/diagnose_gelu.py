#!/usr/bin/env python3
"""Controlled GELU diagnostics using saved binaries, ROI tracing and an I-cache.

The original implementations, simulator binary and main performance results are
not modified. A checked ELF patch replaces sqrt(4) with a constant 2 and a NOP
without moving instructions or changing the number of initialized buffers.
"""
import argparse
import json
import re
import shutil
import statistics
import struct
from pathlib import Path

from run import ROOT, HERE, command, sha


def patch_word(data, address, before, after):
    assert data[:6] == b"\x7fELF\x02\x01", "expected ELF64 little endian"
    phoff = struct.unpack_from("<Q", data, 32)[0]
    size, count = struct.unpack_from("<HH", data, 54)
    for index in range(count):
        kind, _, offset, vaddr, _, filesz, _, _ = struct.unpack_from(
            "<IIQQQQQQ", data, phoff + index * size)
        if kind == 1 and vaddr <= address and address + 4 <= vaddr + filesz:
            position = offset + address - vaddr
            actual = struct.unpack_from("<I", data, position)[0]
            if actual != before:
                raise ValueError(f"binary changed at {address:#x}: {actual:#x} != {before:#x}")
            struct.pack_into("<I", data, position, after)
            return
    raise ValueError(f"unmapped ELF address {address:#x}")


def configuration(destination, original_filter=False):
    source = (HERE / "perf_config.py").read_text()
    source = source.replace("    BadAddr,\n", "    BadAddr,\n    Cache,\n", 1)
    source = source.replace("import m5\n", "import m5\nfrom m5.params import NULL\n", 1)
    # A cache plus a directly connected CPU data port triggers a SnoopFilter
    # assertion in this repository. Disable the optional filter in ALL study
    # scenarios, including the no-cache controls. Coherent snoops remain on.
    if not original_filter:
        source = source.replace("system.membus = SystemXBar()",
                                "system.membus = SystemXBar(snoop_filter=NULL)", 1)
    source = source.replace("args = parser.parse_args()", """parser.add_argument("--icache", action="store_true")
args = parser.parse_args()""", 1)
    source = source.replace("system.cpu.icache_port = system.membus.cpu_side_ports", """if args.icache:
    system.icache = Cache(size="32KiB", assoc=2, tag_latency=1,
                         data_latency=1, response_latency=1,
                         mshrs=4, tgts_per_mshr=8)
    system.cpu.icache_port = system.icache.cpu_side
    system.icache.mem_side = system.membus.cpu_side_ports
else:
    system.cpu.icache_port = system.membus.cpu_side_ports""", 1)
    source = source.replace("m5.instantiate()", """m5.instantiate()
m5.trace.disable()
m5.debug.flags["Branch"].enable()
m5.debug.flags["Fetch"].enable()""", 1)
    source = source.replace("        m5.stats.reset()", "        m5.trace.enable()\n        m5.stats.reset()", 1)
    source = source.replace("        region = cpu_stats()", "        m5.trace.disable()\n        region = cpu_stats()", 1)
    destination.write_text(source)


def trace_summary(trace, regions):
    lines = trace.read_text().splitlines()
    rows = []
    for region in regions:
        selected = []
        for line in lines:
            match = re.match(r"\s*(\d+):", line)
            if match and region["start_tick"] <= int(match[1]) < region["end_tick"]:
                selected.append((int(match[1]), line))
        commits = [(tick, line) for tick, line in selected if "tryToBranch before:" in line]
        forced = [(tick, line) for tick, line in commits if "(forcing)" in line]
        gaps = [(following[0] - current[0]) / 1000
                for current, following in zip(commits, commits[1:])
                if "(forcing)" in current[1]]
        rows.append({
            "repeat": region["repeat"],
            "forced_redirects": len(forced),
            "fetch_requests": sum("Issued fetch request to memory:" in line
                                  for _, line in selected),
            "commit_events": len(commits),
            "cycles_in_gaps_after_forced_commits": sum(gaps),
            "gaps_after_forced_commits": gaps,
            "forced_pcs": [re.search(r"before: (.*?) after:", line)[1]
                           for _, line in forced],
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=ROOT / "example_rvv1.0/build/performance/default")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "example_rvv1.0/build/performance/gelu_diagnosis")
    parser.add_argument("--gem5", type=Path, default=ROOT / "build/RISCV/gem5.opt")
    parser.add_argument("--original-filter-controls", action="store_true",
                        help="run five no-cache controls with the original snoop filter")
    args = parser.parse_args()
    args.input, args.output = args.input.resolve(), args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    work = args.output / "work"
    work.mkdir(exist_ok=True)
    suffix = "_original_filter" if args.original_filter_controls else ""
    results_file = args.output / f"results{suffix}.json"
    results_file.unlink(missing_ok=True)
    config = args.output / f"diagnostic_config{suffix}.py"
    configuration(config, args.original_filter_controls)
    binaries = {}
    reference = None
    gem5_hash = sha(args.gem5)
    for variant in ("ame", "rvv"):
        original = args.input / "gelu" / variant
        result = json.loads((original / "result.json").read_text())
        if result["repeats"] != 3 or sha(original / "target") != result["target_sha256"]:
            raise ValueError("expected verified original three-repetition binaries")
        if gem5_hash != result["files"]["build/RISCV/gem5.opt"]:
            raise ValueError("diagnostic simulator differs from measured simulator")
        golden = (original / "host.txt").read_bytes()
        if reference is not None and reference != golden:
            raise ValueError("AME/RVV golden reports differ")
        reference = golden
        binaries[variant] = (original / "target").read_bytes()
    patched = bytearray(binaries["ame"])
    patches = [
        (0x80000afc, 0x408002b7, 0x400002b7, "four buffer initialized to 2.0 instead of 4.0"),
        (0x80000bac, 0xa340812b, 0x00000013, "msqrt.ew m2,m1 replaced by 4-byte NOP"),
        (0x80000bb0, 0x182001ab, 0x181001ab, "mmul.ew m3,m0,m1 uses loaded constant directly"),
    ]
    for address, before, after, _ in patches:
        patch_word(patched, address, before, after)
    binaries["ame_no_sqrt"] = bytes(patched)
    for name, data in binaries.items():
        (args.output / f"{name}.elf").write_bytes(data)
    # Fixed target/argument paths across scenarios keep startup layout stable.
    scenarios = [
        ("ame_baseline", "ame", 16, False),
        ("ame_no_sqrt", "ame_no_sqrt", 16, False),
        ("ame_matrix6", "ame", 6, False),
        ("ame_matrix1", "ame", 1, False),
        ("rvv_baseline", "rvv", 16, False),
        ("ame_icache", "ame", 16, True),
        ("rvv_icache", "rvv", 16, True),
        ("ame_icache_matrix6", "ame", 6, True),
    ]
    if args.original_filter_controls:
        scenarios = scenarios[:5]
    results = []
    for name, binary, latency, icache in scenarios:
        out = args.output / (name + suffix)
        out.mkdir(exist_ok=True)
        target, guest = work / "target", work / "guest.txt"
        target.write_bytes(binaries[binary])
        target.chmod(0o755)
        guest.unlink(missing_ok=True)
        print(f"[RUN] {name}", flush=True)
        cmd = [args.gem5, "-d", out / "m5out", "--debug-file=trace.txt",
               config, "--cmd", f"{target} {guest}", "--roi-json", out / "roi.json",
               "--vlen", "256", "--matrix-op-lat", str(latency), "--vector-op-lat", "6"]
        if icache:
            cmd.append("--icache")
        command(cmd, out / "simulation.log", 1800)
        if guest.read_bytes() != reference:
            raise ValueError(f"golden mismatch: {name}")
        shutil.copy2(guest, out / "guest.txt")
        roi = json.loads((out / "roi.json").read_text())
        if len(roi["regions"]) != 3:
            raise ValueError(f"incomplete regions: {name}")
        samples = [r["ticks"] / roi["ticks_per_cycle"] for r in roi["regions"]]
        tracing = trace_summary(out / "m5out/trace.txt", roi["regions"])
        row = {"name": name, "binary": binary, "matrix_latency": latency,
               "vector_latency": 6, "icache": icache, "dcache": False,
               "cycles": statistics.median(samples), "samples": samples,
               "target_sha256": sha(target), "output_sha256": sha(guest),
               "trace": tracing, "correct": True}
        results.append(row)
        results_file.write_text(json.dumps({
            "source": str(args.input), "gem5_sha256": gem5_hash,
            "patches": patches, "config_sha256": sha(config),
            "snoop_filter": "original" if args.original_filter_controls else
                            "disabled in all scenarios; coherent broadcast remains enabled",
            "results": results,
        }, indent=2) + "\n")
        print(f"[PASS] {name}: median={row['cycles']:.0f}, samples={samples}, "
              f"redirects={[r['forced_redirects'] for r in tracing]}", flush=True)


if __name__ == "__main__":
    main()
