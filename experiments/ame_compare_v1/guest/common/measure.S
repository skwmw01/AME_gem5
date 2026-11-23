.section .text.measure,"ax"
.option norvc
.option norelax
.globl measure
.type measure,@function
# void measure(void (*kernel)(void), uint64_t counters[4]);
measure:
 addi sp,sp,-48
 sd ra,0(sp)
 sd s0,8(sp)
 sd s1,16(sp)
 sd s2,24(sp)
 sd s3,32(sp)
 mv s0,a0
 mv s1,a1
 fence rw,rw
 li a0,0
 li a1,0
.globl roi_reset
roi_reset:
 .word 0x8000007b
.globl roi_begin
roi_begin:
 rdcycle s2
 rdinstret s3
 jalr ra,s0,0
 fence rw,rw
 rdcycle t0
 rdinstret t1
 sd s2,0(s1)
 sd t0,8(s1)
 sd s3,16(s1)
 sd t1,24(s1)
 li a0,0
 li a1,0
.globl roi_dump
roi_dump:
 .word 0x8200007b
.globl roi_end
roi_end:
 ld ra,0(sp)
 ld s0,8(sp)
 ld s1,16(sp)
 ld s2,24(sp)
 ld s3,32(sp)
 addi sp,sp,48
 ret
.size measure,.-measure
