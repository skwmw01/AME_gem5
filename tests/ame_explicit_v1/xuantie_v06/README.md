# Xuantie v0.6 reference explicit subset

Read encoding.csv, spec_mapping.csv and semantic_contract.md together.
`reference.py` interprets the transposed right operand and low-half-column
conversion independently from S05A. `kernels.S` is generated solely from this
suite's table by the format-only probe generator. Tests X06-0..9 correspond
to table order; every case includes operation number and input/oracle bytes.
The supplied PDF calls signed int8 widening MAC `mmacc.w.b`; this corrects
the implementation plan's `mmaqa.b` mapping without changing experiment code.
