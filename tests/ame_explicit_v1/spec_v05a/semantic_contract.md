# S05A numerical and storage contract

This is a spec-v0.5a reference **research subset**. Native mtype semantics and
native OP-M32 0x77 compatibility are deliberately outside this implementation.
CUSTOM-2 0x5B encodes ten fixed complete type tuples. Only AMENLEN=4,
AMEUDSZ=32 are supported; other shapes fault before destination access.

Add/max use 16 little-endian 32-bit elements in each M's low 64 bytes. MAC
multiplies row-major A[4][16] by B[16][4] for int8, or A[4][8] by B[8][4]
for FP16/BF16. The destination Acc[4][4] is both read and written. Integer
results are modulo 2^32 and never set saturation. Signed/unsigned comparisons
have distinct encodings. Inputs are snapshotted before writeback.

Half-to-float expands all 32 source halves, indices 0..15 into md and 16..31
into md+1. Both destinations are declared as read/write operands to preserve
unused container bytes. md=30 is legal; md=31 decodes as Unknown. Both targets
are validated before any destination access. Overlapping sources are supported.

Float operations always use RNE regardless of scalar FRM or type descriptors.
Subnormals are preserved; underflow is detected after rounding and requires
inexactness (UF|NX). Overflow produces signed infinity and OF|NX. Ordinary
inexact rounding produces NX. MAC performs ascending-k FP32 FMA after exact
half/BF16 expansion. FP32 NaNs canonicalize to 0x7fc00000, sNaNs raise NV.
Float-to-int rounds first, then clips invalid negative inputs to INT32_MIN,
and positive invalid/NaN to INT32_MAX, setting NV alone for that element.
Other elements' and previous instructions' flags remain sticky.

The S05A-specific floating environment saves/restores all SoftFloat global
state. Only AMEFFLAGS and AME dirty state change; scalar fcsr, Md/Ad, amestype
and saturation state do not. These choices are experimental adaptations.
