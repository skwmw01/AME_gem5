/* Ztt v0.6: identical register allocation and loop macro in both schemes. */
    .option norvc
    .option norelax
    .text

/* Sized ELF symbols map every emitted instruction (including li expansion)
 * to a category. They are metadata, not guest instructions. */
    .macro ins category, instruction:vararg
    .globl pi_\category\()_\@
pi_\category\()_\@:
    \instruction
    .size pi_\category\()_\@, . - pi_\category\()_\@
    .endm

    .macro setup input_type, output_type, blocks
    ins type_prepare, li t0, \input_type
    .if \input_type == \output_type
    ins type_prepare, mv t1, t0
    .else
    ins type_prepare, li t1, \output_type
    .endif
    ins other_prepare, li t2, \blocks
    .endm

    .macro body name
    .globl \name\()_body
\name\()_body:
    ins type_init, msettyp m0, t0
    ins type_init, msettyp m4, t0
    ins type_init, msettyp m8, t1
    ins type_init, asettyp acc0, t1
    ins other_prepare, mv t4, a0
    ins other_prepare, mv t5, a1
    ins other_prepare, mv t6, a4
.Louter_\@:
    ins control_address, mv a0, t4
    ins control_address, mv a1, t5
    ins other_prepare, mv t3, t2
.Linner_\@:
    ins matrix_move, mls.rm m0, a0
    ins matrix_move, mls.rm m4, a1
    ins compute, mmulacc.2d acc0, m0, m4
    ins control_address, addi a0, a0, 64
    ins control_address, addi a1, a1, 64
    ins control_address, addi t3, t3, -1
    ins control_address, bnez t3, .Linner_\@
    ins control_address, addi t6, t6, -1
    ins control_address, bnez t6, .Louter_\@
    ins matrix_move, mmov.m.a m8, acc0
    ins matrix_move, mss.rm m8, a2
    ins call_return, ret
    .size \name\()_body, . - \name\()_body
    .endm

    .globl run_specialized
    .type run_specialized, @function
run_specialized:
    ins dispatch, beqz a3, .Lspec_fp32
    ins dispatch, li a6, 1
    ins dispatch, beq a3, a6, .Lspec_int32
    /* INT8 is the final fall-through in both schemes. */
    .globl gemm_int8
    .type gemm_int8, @function
gemm_int8:
    setup 0x40000008, 0x40000020, 1
    body gemm_int8
    .size gemm_int8, . - gemm_int8
    .globl gemm_fp32
    .type gemm_fp32, @function
gemm_fp32:
.Lspec_fp32:
    setup 0x20300120, 0x20300120, 4
    body gemm_fp32
    .size gemm_fp32, . - gemm_fp32
    .globl gemm_int32
    .type gemm_int32, @function
gemm_int32:
.Lspec_int32:
    setup 0x40000020, 0x40000020, 4
    body gemm_int32
    .size gemm_int32, . - gemm_int32
    .size run_specialized, . - run_specialized

    .globl run_shared
    .type run_shared, @function
run_shared:
    ins dispatch, beqz a3, .Lfp32
    ins dispatch, li a6, 1
    ins dispatch, beq a3, a6, .Lint32
    setup 0x40000008, 0x40000020, 1
    ins dispatch, j shared_body
.Lfp32:
    setup 0x20300120, 0x20300120, 4
    ins dispatch, j shared_body
.Lint32:
    setup 0x40000020, 0x40000020, 4
    body shared
    .size run_shared, . - run_shared

/* The public measurement wrappers have the same five run arguments, plus
 * an out-of-band pointer to {instret_before, instret_after} in a5.
 * Stack operations and marker setup are outside the interval. */
    .macro measure scheme
    .globl measure_\scheme
    .type measure_\scheme, @function
measure_\scheme:
    addi sp, sp, -32
    sd ra, 0(sp)
    sd s0, 8(sp)
    sd s1, 16(sp)
    mv s1, a5
    .globl measure_\scheme\()_begin
measure_\scheme\()_begin:
    ins auxiliary, rdinstret s0
    ins call_return, jal ra, run_\scheme
    .globl measure_\scheme\()_end
measure_\scheme\()_end:
    rdinstret t0
    sd s0, 0(s1)
    sd t0, 8(s1)
    ld ra, 0(sp)
    ld s0, 8(sp)
    ld s1, 16(sp)
    addi sp, sp, 32
    ret
    .size measure_\scheme, . - measure_\scheme
    .endm
    measure specialized
    measure shared

/* Standard gem5 work-item pseudo-ops only gate tracing of the whole batch.
 * They never occur inside a per-call measurement interval. */
    .globl batch_begin
batch_begin:
    li a0, 0
    li a1, 0
    .long 0xb400007b
    ret
    .globl batch_end
batch_end:
    li a0, 0
    li a1, 0
    .long 0xb600007b
    ret
