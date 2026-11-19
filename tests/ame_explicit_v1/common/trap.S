.text
.balign 4
.globl trap_handler
trap_handler:
    addi sp, sp, -32
    sd t0, 0(sp)
    sd t1, 8(sp)
    la t0, traps
    ld t1, 0(t0)
    addi t1, t1, 1
    sd t1, 0(t0)
    la t0, cause
    csrr t1, mcause
    sd t1, 0(t0)
    la t0, trap_value
    csrr t1, mtval
    sd t1, 0(t0)
    la t0, trap_pc
    csrr t1, mepc
    sd t1, 0(t0)
    addi t1, t1, 4
    csrw mepc, t1
    ld t0, 0(sp)
    ld t1, 8(sp)
    addi sp, sp, 32
    mret
