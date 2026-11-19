# X06 numerical and storage contract

This is a Xuantie v0.6 reference **research subset**, not binary compatibility.
CUSTOM-0 0x0B; ten complete explicit type tuples in encoding.csv. No Md/Ad,
amestype or mtype affects calculation. AMENLEN=4 and AMEUDSZ=32 only.

All operands use contiguous little-endian low 64 bytes. Add/max operate on
16 words. macbt reads A[4][16] and BT[4][16] for signed bytes, or A[4][8]
and BT[4][8] for halves; output is Acc[4][4]. The k loop is ascending.
The FP16 conversion reads indices row*8+col, col=0..3, not the first 16
linear halves. Unspecified container bytes are retained. Inputs are snapshots.

Integer add/MAC wrap modulo 2^32 without saturation. Max interprets the
selected signedness explicitly. Fixed RNE, subnormals retained, tininess after
rounding. FP16/BF16 widen exactly before each fused FP32 multiplication/addition;
each FMA rounds once to FP32. NaN results canonicalize to 0x7fc00000, signaling
NaNs raise NV. Inexact rounding raises NX; overflow rounds to signed infinity
with OF|NX; tiny inexact results raise UF|NX; exact subnormals do not raise UF.

Float-to-int rounds to nearest even before range checking. Invalid positive
and all NaNs yield 0x7fffffff; invalid negative values yield 0x80000000. An
invalid element raises NV without NX, but does not erase another element's NX.
These clipping rules and ordered FMA are experimental choices, not claims of
native architectural equivalence. Signed zero follows IEEE RNE addition/FMA.

SoftFloat rounding/tininess/flags are saved and restored by the X06 environment.
Only AMEFFLAGS sticky bits and AME dirty state are committed after calculation;
fcsr, Md/Ad, amestype and AMEXSAT are unchanged. Permission, ownership and shape
checks occur before writable operands are obtained.
