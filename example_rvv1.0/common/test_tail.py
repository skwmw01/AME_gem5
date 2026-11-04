#!/usr/bin/env python3
"""Exercise non-square GEMM and VL tails against an independent FP32 golden."""
import json
import random
import struct
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
directory = root / "build" / "tail"
directory.mkdir(parents=True, exist_ok=True)
rng = random.Random(20261104)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


for m, k, n in ((1, 1, 1), (3, 5, 13), (5, 7, 19)):
    a = [f32(rng.uniform(-3, 3)) for _ in range(m * k)]
    b = [f32(rng.uniform(-3, 3)) for _ in range(k * n)]
    c = [f32(rng.uniform(-1, 1)) for _ in range(m * n)]
    values = c.copy()
    for row in range(m):
        for col in range(n):
            for depth in range(k):
                i = row * n + col
                values[i] = f32(values[i] + f32(a[row*k+depth] * b[depth*n+col]))
    input_path = directory / f"input-{m}-{k}-{n}.json"
    reference_path = directory / f"reference-{m}-{k}-{n}.json"
    input_path.write_text(json.dumps({
        "name": f"RVV FP32 tail {m}x{k}x{n}", "dtype": "f32",
        "shape": [m, k, n], "a": a, "b": b, "c": c,
    }))
    reference_path.write_text(json.dumps({
        "dtype": "f32", "shape": [m, n], "values": values,
    }))
    for vlen in (128, 256, 512):
        subprocess.run([
            "make", "--no-print-directory", "-C", str(root / "gemm_fp32"),
            "test", "GOLDEN=reference", f"VLEN={vlen}",
            f"MATRIX_INPUT={input_path}", f"MATRIX_REFERENCE={reference_path}",
            f"BUILD_DIR={directory / f'{m}-{k}-{n}-vlen{vlen}'}",
        ], check=True)
for case in ("gemm_int8", "gemm_mixed"):
    for vlen in (128, 256, 512):
        subprocess.run([
            "make", "--no-print-directory", "-C", str(root / case),
            "test", "GOLDEN=host", f"VLEN={vlen}",
            "EXTRA_CFLAGS=-DZTT_LLM_M=13 -DZTT_LLM_K=13 -DZTT_LLM_N=13",
            f"BUILD_DIR={directory / f'{case}-13-vlen{vlen}'}",
        ], check=True)
print("[PASS] 9 FP32 and 6 INT8 dimension/VLEN combinations")
