OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY { ram (rwx) : ORIGIN = 0x80000000, LENGTH = 128M }
SECTIONS {
 .startup 0x80000000 : { KEEP(*(.text.init)) } > ram
 .measure 0x80010000 : { KEEP(*(.text.measure)) } > ram
 .compute 0x80020000 : { *(.text.compute*) } > ram
 .types 0x80024000 : { *(.text.type*) } > ram
 .moves 0x80028000 : { *(.text.move*) } > ram
 .layout 0x80030000 : { *(.text.layout*) } > ram
 .w1_0 0x80040000 : { *(.text.kernel.w1_0) } > ram
 .w1_1 0x80041000 : { *(.text.kernel.w1_1) } > ram
 .w1_2 0x80042000 : { *(.text.kernel.w1_2) } > ram
 .w1_3 0x80043000 : { *(.text.kernel.w1_3) } > ram
 .w1_4 0x80044000 : { *(.text.kernel.w1_4) } > ram
 .w1_5 0x80045000 : { *(.text.kernel.w1_5) } > ram
 .w1_6 0x80046000 : { *(.text.kernel.w1_6) } > ram
 .w1_7 0x80047000 : { *(.text.kernel.w1_7) } > ram
 .w1_8 0x80048000 : { *(.text.kernel.w1_8) } > ram
 .w1_9 0x80049000 : { *(.text.kernel.w1_9) } > ram
 .kernels 0x80050000 : { *(.text.kernel*) } > ram
 .text 0x80100000 : { *(.text .text.*) } > ram
 .rodata 0x80200000 : { *(.rodata .rodata.*) *(.srodata .srodata.*) } > ram
 .data 0x80300000 : { __data_start = .; PROVIDE(__global_pointer$ = . + 0x800); *(.data .data.*) *(.sdata .sdata.*) __data_end = .; } > ram
 .bss 0x80400000 (NOLOAD) : ALIGN(64) { __bss_start = .; *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON) . = ALIGN(64); __bss_end = .; } > ram
 .input 0x81000000 (NOLOAD) : { *(.input) } > ram
 .output 0x81800000 (NOLOAD) : { *(.output) } > ram
 .scratch 0x82000000 (NOLOAD) : { *(.scratch) } > ram
 .stack 0x82800000 (NOLOAD) : { __stack_bottom = .; . += 4M; __stack_top = .; } > ram
 /DISCARD/ : { *(.comment) *(.note .note.*) *(.eh_frame .eh_frame.*) }
 ASSERT(SIZEOF(.startup) < 0x10000, "startup overlaps measurement")
 ASSERT(SIZEOF(.measure) < 0x10000, "measurement overlaps kernels")
 ASSERT(SIZEOF(.kernels) < 0xb0000, "kernels overlap runtime")
 ASSERT(SIZEOF(.text) < 0x100000, "runtime overlaps rodata")
 ASSERT(SIZEOF(.rodata) < 0x100000, "rodata overlaps data")
 ASSERT(SIZEOF(.input) < 0x800000, "input overflow")
 ASSERT(SIZEOF(.output) < 0x800000, "output overflow")
 ASSERT(SIZEOF(.scratch) < 0x800000, "scratch overflow")
}
