# spec-v0.5a reference explicit subset

Read encoding.csv, spec_mapping.csv and semantic_contract.md together.
`reference.py` owns the row-major B indexing and full-source two-register
widening. `kernels.S` is emitted from this suite's separate encoding table.
S05A-0..9 correspond to table order. Native spec-v0.5a uses mtype.mfp16 to
select FP16/BF16; the experimental fixed encodings intentionally replace that
choice and must not be presented as native ISA compatibility.
