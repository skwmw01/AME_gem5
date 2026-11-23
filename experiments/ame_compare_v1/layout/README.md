# Layout implementation

Logical tile and reference-side pack mappings: `tools/model.py:pack_mac`.
Guest timed layouts: `guest/common/bench.c` functions pack_tile, pack_half,
pack_gemm, pack_widen and scatter. Host reversibility checks:
`tools/layout_checks.py`. Simulator-executed coordinate, widening and immediate
second-output checks: `guest/common/gates.c` and `tools/gates.py`.

P uses q*16+i*4+r / q*16+j*4+r; X06 uses i*K0+k / j*K0+k;
S05A uses i*K0+k / k*4+j. End-to-end source matrices use their real I8 or
half/BF16 byte widths. Padding occurs inside guest ROI, with useful and padded
MACs recorded separately. No host packing time enters target timing.
