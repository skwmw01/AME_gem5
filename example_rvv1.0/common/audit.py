#!/usr/bin/env python3
"""Audit actual linked instructions, including rejection of AME opcodes."""
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text()
instructions = re.findall(
    r"^\s*[0-9a-f]+:\s+(?:[0-9a-f]{2,8}\s+)+([a-z][a-z0-9_.]*)",
    text,
    re.MULTILINE,
)
missing = {group for group in sys.argv[2:]
           if not set(group.split("/")) & set(instructions)}
forbidden = [op for op in instructions if (
    op.startswith("ame.") or op.endswith((".ew", ".2d", ".row", ".rm"))
    or op in {"msettyp", "asettyp"} or op.startswith("mmov.")
)]
if missing or forbidden or "<unknown>" in text:
    raise SystemExit(
        f"instruction audit failed: missing={sorted(missing)}, "
        f"AME={forbidden}, unknown={'<unknown>' in text}"
    )
if not any(op in {"vsetvli", "vsetivli"} for op in instructions):
    raise SystemExit("no RVV vector configuration instruction found")
print("[PASS] standard RVV instructions present; no AME/unknown instructions")
