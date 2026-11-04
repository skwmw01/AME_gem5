#!/usr/bin/env python3
"""Require executed vector instructions and zero executed AME operations."""
import re
import sys
from pathlib import Path

stats = Path(sys.argv[1]).read_text()


def value(name):
    match = re.search(rf"(?m)^{re.escape(name)}\s+(\d+)\s", stats)
    if not match:
        raise SystemExit(f"missing gem5 execution statistic: {name}")
    return int(match.group(1))


prefix = "system.cpu.commitStats0."
vectors = value(prefix + "numVecInsts")
matrix = sum(value(prefix + "committedInstType::" + kind)
             for kind in ("Matrix", "MatrixMov", "MatrixOP"))
if vectors == 0 or matrix != 0:
    raise SystemExit(f"execution audit failed: RVV={vectors}, AME={matrix}")
print(f"[PASS] executed RVV={vectors}, AME={matrix}")
