#!/usr/bin/env python3
"""Build, validate and measure original AME and RVV operator implementations.

Generated instrumented copies live under build/performance; neither original
operator tree is rewritten. The default is VLEN=256 and three repetitions.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ("gemm_fp32", "gemm_int8", "gemm_mixed",
         "gemm_mixed_source_types", "gelu", "softmax", "rmsnorm",
         "rope", "mha", "ffn", "gemm_fp32_config")


def repository_head():
    """Read checkout provenance even in the minimal container without git."""
    git_dir = ROOT / ".git"
    if git_dir.is_file():
        git_dir = (ROOT / git_dir.read_text().strip().split(": ", 1)[1]).resolve()
    if not (git_dir / "HEAD").exists():
        return "unknown (source archive)"
    head = (git_dir / "HEAD").read_text().strip()
    if not head.startswith("ref: "):
        return head
    ref = head.removeprefix("ref: ")
    common_dir = git_dir
    if (git_dir / "commondir").exists():
        common_dir = (git_dir / (git_dir / "commondir").read_text().strip()).resolve()
    if (common_dir / ref).exists():
        return (common_dir / ref).read_text().strip()
    packed = common_dir / "packed-refs"
    if packed.exists():
        for line in packed.read_text().splitlines():
            fields = line.split()
            if len(fields) == 2 and fields[1] == ref:
                return fields[0]
    return "unknown (unresolved ref)"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def command(args, log, timeout=1200):
    args = [str(x) for x in args]
    with Path(log).open("w") as f:
        f.write("COMMAND: " + __import__("shlex").join(args) + "\n")
        f.flush()
        try:
            subprocess.run(args, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT,
                           check=True, timeout=timeout)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            raise RuntimeError(f"command failed; inspect {log}") from None


def function_bounds(source, name, last=False):
    needle = "\n" + name + "("
    start = source.rindex(needle) if last else source.index(needle)
    opening = source.index("{", start)
    depth = 1
    for i in range(opening + 1, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if not depth:
                return opening, i
    raise ValueError(f"unterminated function {name}")


def instrument(source, case, variant):
    """Insert precisely documented kernel boundaries; fail on source drift."""
    if case == "gemm_mixed_source_types":
        if variant == "ame":
            source = source.replace('#include "span_checks.h"\n', "")
            source = source.replace('#include "unsupported_checks.h"\n', "")
            assert source.count("ztt_gemm_report_init(&report, 14, 17);") == 1
            source = source.replace("ztt_gemm_report_init(&report, 14, 17);",
                                    "ztt_gemm_report_init(&report, 14, 14);")
            first = source.index('    case_names[14] =')
            last = source.index('#if defined(__riscv)\n    __asm__ volatile("ame.release"', first)
            source = source[:first] + source[last:]
        opening, end = function_bounds(source, "execute", last=True)
        source = source[:end] + "    bench_end();\n" + source[end:]
        source = source[:opening + 1] + "\n    bench_begin();" + source[opening + 1:]
        marker = "    return ztt_gemm_report_write(path, &report, case_names);"
        assert source.count(marker) == 1
        source = source.replace(marker, "    if (bench_repeat + 1 < BENCH_REPEATS) return 1;\n" + marker)
        source += '''
uint64_t bench_mixed_hash(void)
{
    const uint8_t *p = (const uint8_t *)&report;
    uint64_t hash = UINT64_C(1469598103934665603);
    for (unsigned i = 0; i < sizeof(report); ++i) {
        hash ^= p[i];
        hash *= UINT64_C(1099511628211);
    }
    return hash;
}
'''
    elif case == "rope":
        opening, end = function_bounds(source, "ztt_llm_rope_fp32_tile")
        region = source[opening:end]
        region = region.replace("#if defined(__riscv)\n", "#if defined(__riscv)\n    bench_begin();\n", 1)
        if variant == "ame":
            assert region.count("return ztt_llm_release();") == 1
            region = region.replace("return ztt_llm_release();",
                                    "uint64_t status = ztt_llm_release();\n    bench_end();\n    return status;")
        else:
            before, after = region.split("#else", 1)
            assert before.count("return 0;") == 1
            region = before.replace("return 0;", "bench_end();\n    return 0;") + "#else" + after
        source = source[:opening] + region + source[end:]
    else:
        opening, end = function_bounds(source, "ztt_llm_run_case")
        region = source[opening:end]
        finish = region.index("    result->output =")
        if case == "mha" and variant == "rvv":
            start = region.index("\n    for (unsigned head = 0; head < heads; ++head)") + 1
        else:
            start = region.index("#if defined(__riscv)\n")
        assert start < finish
        region = region[:finish] + "    bench_end();\n" + region[finish:]
        region = region[:start] + "    bench_begin();\n" + region[start:]
        source = source[:opening] + region + source[end:]
    return '#include "roi.h"\n' + source


def driver(source, case):
    if case == "gemm_mixed_source_types":
        return '''#include <stdio.h>
#include "roi.h"
volatile unsigned bench_repeat;
int ztt_mixed_run_suite(const char *path);
uint64_t bench_mixed_hash(void);
int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    uint64_t previous = 0;
    for (bench_repeat = 0; bench_repeat < BENCH_REPEATS; ++bench_repeat) {
        if (!ztt_mixed_run_suite(argv[1])) return 1;
        uint64_t hash = bench_mixed_hash();
        if (bench_repeat && hash != previous) return 3;
        previous = hash;
    }
    return 0;
}
'''
    marker = "    result.status = ztt_llm_run_case(&result);"
    assert source.count(marker) == 1
    replacement = '''    uint64_t previous = 0;
    for (bench_repeat = 0; bench_repeat < BENCH_REPEATS; ++bench_repeat) {
        result.status = ztt_llm_run_case(&result);
        if (result.status) return 1;
        uint64_t hash = ztt_llm_hash(result.output,
            (uint64_t)result.element_count * result.element_bytes);
        if (bench_repeat && hash != previous) return 3;
        previous = hash;
    }'''
    source = source.replace(marker, replacement)
    source = source.replace("int\nmain(", "volatile unsigned bench_repeat;\n\nint\nmain(", 1)
    return '#include "roi.h"\n' + source


def measure(args, case, variant):
    original_case = "gemm_fp32" if case == "gemm_fp32_config" else case
    source_root = ROOT / ("example" if variant == "ame" else "example_rvv1.0")
    case_dir = source_root / original_case
    common = source_root / "common"
    out = args.output / case / variant
    out.mkdir(parents=True, exist_ok=True)
    operator = instrument((case_dir / "operators.c").read_text(), original_case, variant)
    main = driver((case_dir / "main.c").read_text(), original_case)
    (out / "operators.c").write_text(operator)
    (out / "main.c").write_text(main)
    compiler = args.ame_clang if variant == "ame" else args.rvv_clang
    version = subprocess.check_output([str(compiler), "--version"], text=True)
    resource = subprocess.check_output([str(compiler), "-print-resource-dir"], text=True).strip()
    runtime = ROOT / "example/common"
    sources = [out / "main.c", out / "operators.c"]
    if variant == "rvv":
        sources.append(common / "rvv_kernels.c")
    dependencies = sources + list(common.glob("*.h")) + list(case_dir.glob("*.h"))
    dependencies += list(runtime.glob("*")) + list((runtime / "include").glob("*.h"))
    dependencies += [HERE / "roi.h", HERE / "perf_config.py", HERE / "run.py", Path(args.gem5)]
    if case == "gemm_fp32_config":
        dependencies += list((case_dir / "config").glob("*.json"))
    manifest = {
        "case": case, "variant": variant, "compiler": version,
        "vlen": args.vlen, "matrix_op_lat": args.matrix_op_lat,
        "vector_op_lat": args.vector_op_lat, "repeats": args.repeats,
        "ame_march": args.ame_march, "ame_features": args.ame_features,
        "linker_version": subprocess.check_output([args.linker, "--version"], text=True),
        "host_cc_version": subprocess.check_output([args.host_cc, "--version"], text=True),
        "files": {str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p): sha(p)
                  for p in dependencies if p.is_file()},
    }
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    result_file = out / "result.json"
    if args.resume and result_file.exists():
        previous = json.loads(result_file.read_text())
        artifacts_match = (
            (out / "target").is_file() and (out / "guest.txt").is_file()
            and (out / "host.txt").is_file() and (out / "roi.json").is_file()
            and sha(out / "target") == previous.get("target_sha256")
            and sha(out / "guest.txt") == previous.get("output_sha256")
            and sha(out / "roi.json") == previous.get("roi_sha256")
            and (out / "guest.txt").read_bytes() == (out / "host.txt").read_bytes()
        )
        if previous.get("fingerprint") == fingerprint and artifacts_match:
            print(f"[REUSE] {case}/{variant}", flush=True)
            return previous
    # Invalidate old success before any potentially failing build or run.
    result_file.unlink(missing_ok=True)
    guest_report, host_report = out / "guest.txt", out / "host.txt"
    for p in (guest_report, host_report, out / "roi.json"):
        p.unlink(missing_ok=True)
    includes = [f"-I{common}", f"-I{case_dir}", f"-I{HERE}"]
    defines = [f"-DBENCH_REPEATS={args.repeats}"]
    if case == "gemm_fp32_config":
        generated = out / "matrix_input.h"
        command([sys.executable, common / "matrix_case.py", "header", "--input",
                 case_dir / "config/matrix_input.json", "--output", generated], out / "matrix.log")
        defines += ["-DZTT_EXTERNAL_MATRIX_INPUT", "-include", str(generated)]
    common_flags = ["-O2", "-g", "-Wall", "-Wextra", "-Werror", "-ffp-contract=off"]
    command([args.host_cc, *common_flags, *includes, *defines, *sources, "-lm",
             "-o", out / "host"], out / "build-host.log")
    command([out / "host", host_report], out / "run-host.log")
    march = args.ame_march if variant == "ame" else "rv64gcv"
    compile_cmd = [compiler, "-target", "riscv64-unknown-elf", "-resource-dir", resource,
                   f"-march={march}", "-mabi=lp64d", *common_flags,
                   "-ffreestanding", "-fno-builtin", "-mcmodel=medany",
                   "-ffunction-sections", "-fdata-sections", "-fno-vectorize",
                   "-fno-slp-vectorize", *includes, f"-I{runtime / 'include'}", *defines,
                   runtime / "crt0.S", runtime / "runtime.c", *sources,
                   f"--ld-path={args.linker}", "-nostdlib", "-static",
                   f"-Wl,-T,{runtime / 'link.ld'}", "-Wl,--gc-sections", "-o", out / "target"]
    command(compile_cmd, out / "build-target.log")
    # The AME disassembler also understands standard V instructions.
    command([args.objdump, "-d", f"--mattr={args.ame_features if variant == 'ame' else '+v'}",
             out / "target"], out / "disassembly.txt")
    disassembly = (out / "disassembly.txt").read_text()
    if variant == "ame" and "ame.acquire" not in disassembly:
        raise RuntimeError(f"AME code missing from {case}")
    if variant == "rvv" and ("ame.acquire" in disassembly or "msettyp" in disassembly):
        raise RuntimeError(f"AME instruction found in RVV {case}")
    print(f"[RUN] {case}/{variant}: {args.repeats} repetitions", flush=True)
    command([args.gem5, "-d", out / "m5out", HERE / "perf_config.py",
             "--cmd", f"{out / 'target'} {guest_report}", "--vlen", args.vlen,
             "--matrix-op-lat", args.matrix_op_lat, "--vector-op-lat", args.vector_op_lat,
             "--max-ticks", args.max_ticks, "--roi-json", out / "roi.json"],
            out / "simulation.log", args.timeout)
    if guest_report.read_bytes() != host_report.read_bytes():
        raise RuntimeError(f"correctness mismatch: {case}/{variant}")
    data = json.loads((out / "roi.json").read_text())
    region_count = 336 if case == "gemm_mixed_source_types" else 1
    samples = []
    fields = ("ticks", "instructions", "ops", "vector_instructions",
              "matrix_instructions", "loads", "stores")
    if len(data["regions"]) != region_count * args.repeats:
        raise RuntimeError(f"unexpected region count: {case}/{variant}")
    for repeat in range(args.repeats):
        regions = [r for r in data["regions"] if r["repeat"] == repeat]
        if len(regions) != region_count:
            raise RuntimeError(f"incomplete repetition: {case}/{variant}/{repeat}")
        sample = {f: sum(r[f] for r in regions) for f in fields}
        sample["cycles"] = sample["ticks"] / data["ticks_per_cycle"]
        if variant == "rvv" and (sample["vector_instructions"] <= 0 or sample["matrix_instructions"]):
            raise RuntimeError(f"RVV execution audit failed: {case}")
        if variant == "ame" and sample["matrix_instructions"] <= 0:
            raise RuntimeError(f"AME execution audit failed: {case}")
        samples.append(sample)
    result = dict(manifest, fingerprint=fingerprint, samples=samples,
                  cycles=statistics.median(s["cycles"] for s in samples),
                  min_cycles=min(s["cycles"] for s in samples),
                  max_cycles=max(s["cycles"] for s in samples),
                  roi_count_per_repeat=region_count, correct=True,
                  target_sha256=sha(out / "target"), output_sha256=sha(guest_report),
                  roi_sha256=sha(out / "roi.json"),
                  total_guest_ticks=data["total_ticks"])
    result_file.write_text(json.dumps(result, indent=2) + "\n")
    print(f"[PASS] {case}/{variant}: {result['cycles']:,.0f} cycles, golden matches", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--variants", nargs="+", choices=("ame", "rvv"), default=["ame", "rvv"])
    parser.add_argument("--vlen", type=int, choices=(128, 256, 512, 1024), default=256)
    parser.add_argument("--matrix-op-lat", type=int, default=16)
    parser.add_argument("--vector-op-lat", type=int, default=6)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--max-ticks", type=int, default=30000000000000)
    parser.add_argument("--output", type=Path, default=ROOT / "example_rvv1.0/build/performance/default")
    parser.add_argument("--gem5", type=Path, default=ROOT / "build/RISCV/gem5.opt")
    parser.add_argument("--ame-clang", type=Path, default=ROOT / "toolchain/install/bin/clang")
    parser.add_argument("--rvv-clang", type=Path, default=Path(shutil.which("clang-18") or "clang-18"))
    parser.add_argument("--objdump", type=Path, default=ROOT / "toolchain/install/bin/llvm-objdump")
    parser.add_argument("--linker", type=Path, default=Path(shutil.which("ld.lld-18") or "ld.lld-18"))
    parser.add_argument("--host-cc", default="cc")
    parser.add_argument("--ame-march", default="rv64gcv_xxiangshanztt")
    parser.add_argument("--ame-features", default="+xxiangshanztt")
    parser.add_argument("--resume", action="store_true", help="reuse only fingerprint-matching successful results")
    args = parser.parse_args()
    if min(args.repeats, args.jobs, args.matrix_op_lat, args.vector_op_lat) <= 0:
        parser.error("counts and latencies must be positive")
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    for path in (args.gem5, args.objdump, args.linker,
                 *([args.ame_clang] if "ame" in args.variants else []),
                 *([args.rvv_clang] if "rvv" in args.variants else [])):
        if not path.is_file():
            parser.error(f"missing tool: {path}; see setup_toolchain.py and Dockerfile")
    environment_file = args.output / "environment.json"
    if not args.resume or not environment_file.exists():
        environment = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "os": Path("/etc/os-release").read_text(),
            "python": platform.python_version(),
            "git_head": repository_head(),
            "host_cc": subprocess.check_output([args.host_cc, "--version"], text=True).splitlines()[0],
            "lld": subprocess.check_output([args.linker, "--version"], text=True).splitlines()[0],
        }
        for variant in args.variants:
            compiler = args.ame_clang if variant == "ame" else args.rvv_clang
            environment[variant + "_clang"] = subprocess.check_output(
                [compiler, "--version"], text=True).splitlines()[0]
        environment_file.write_text(json.dumps(environment, indent=2) + "\n")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(measure, args, case, variant)
                   for case in args.cases for variant in args.variants]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    # Stronger than independent golden checks: both implementations must emit
    # identical complete result reports for the same selected workload.
    for case in args.cases:
        pair = [r for r in results if r["case"] == case]
        if len(pair) == 2 and pair[0]["output_sha256"] != pair[1]["output_sha256"]:
            raise RuntimeError(f"AME/RVV output reports differ: {case}")
    (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"[PASS] {len(results)} measured binaries; results: {args.output / 'results.json'}")


if __name__ == "__main__":
    main()
