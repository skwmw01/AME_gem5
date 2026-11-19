/* Frozen compatibility ELF: RVV, scalar FRM, m5ops and semihosting. */
#include <stdint.h>
#include <stdio.h>
static uint32_t input[4] = {1,0x7fffffff,0xffffffff,0x80000000};
static uint32_t output[4];
int main(int argc,char **argv)
{
    if(argc<2) return 2;
    FILE *report=fopen(argv[1],"w");
    if(!report) return 3;
    __asm__ volatile("vsetivli zero,4,e32,m1,ta,ma\n vle32.v v0,(%0)\n"
        "vadd.vv v2,v0,v0\n vse32.v v2,(%1)"::"r"(input),"r"(output):"memory");
    int bad=0;
    for(unsigned n=0;n<4;++n) {
        bad |= output[n] != input[n]*2;
        fprintf(report,"rvv %u %x\n",n,output[n]);
    }
    for(unsigned rm=0;rm<5;++rm) {
        uint64_t result,flags;
        __asm__ volatile("csrw frm,%2\n csrw fflags,zero\n"
            "fmv.w.x ft0,%3\n fmv.w.x ft1,%4\n fadd.s ft2,ft0,ft1,dyn\n"
            "fmv.x.w %0,ft2\n csrr %1,fflags"
            :"=r"(result),"=r"(flags):"r"((uint64_t)rm),"r"(0x3f800000UL),"r"(0x33800000UL)
            :"ft0","ft1","ft2","memory");
        bad |= result != (rm>=3 ? 0x3f800001UL : 0x3f800000UL) || flags != 1;
        fprintf(report,"scalar %u %lx %lu\n",rm,result,flags);
    }
    /* Original CUSTOM-3 M5FUNC=0x41; final statistics must use the last block. */
    __asm__ volatile("li a0,0\n li a1,0\n .word 0x8200007b":::"a0","a1","memory");
    fprintf(report,"status %u\n",bad);
    fclose(report);
    return bad;
}
