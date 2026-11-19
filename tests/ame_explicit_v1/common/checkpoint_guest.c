#define main numeric_main
#include "guest.c"
#undef main
const struct Input test_data[1] = {{0}};
const uint32_t test_count = 1;
static void snapshot(void)
{
    __asm__ volatile("li a0,0\n li a1,0\n .word 0x8600007b"
                     :::"a0","a1","memory");
}
int main(int argc,char **argv)
{
    if(argc<2) return 2;
    FILE *out=fopen(argv[1],"w");
    if(!out) return 3;
    __asm__ volatile("csrw mtvec,%0"::"r"(trap_handler):"memory");
    memset(poison,0xa5,64);
    struct Input in={0};
    memset(in.a,0x33,64); memset(in.b,0x55,64); memset(in.c,0x77,64);
    #ifdef SHAPE_TEST
    const unsigned scenarios=1;
#else
    const unsigned scenarios=2;
#endif
    for(unsigned disabled=0;disabled<scenarios;++disabled) {
        __asm__ volatile("li t0,0x3c\n ame.acquire t1,t0":::"t0","t1","memory");
        setup(&in,0,0);
#ifndef SHAPE_TEST
        __asm__ volatile("ame.release":::"memory");
        if(disabled) {
            const uint64_t ms=3UL<<23;
            __asm__ volatile("csrc mstatus,%0"::"r"(ms):"memory");
        }
#endif
        snapshot();
        for(unsigned op=0;op<10;++op) {
            traps=cause=trap_pc=trap_value=0;
            kernels[op][0]();
            int ok=traps==1 && cause==2 && trap_pc==(uintptr_t)kernels[op][0] &&
                trap_value==*(const uint32_t *)(uintptr_t)kernels[op][0];
            snapshot();
            fprintf(out,"%u %u %u\n",disabled,op,ok);
        }
        const uint64_t ms=1UL<<23;
        __asm__ volatile("csrs mstatus,%0"::"r"(ms):"memory");
    }
    fclose(out);
    return 0;
}
