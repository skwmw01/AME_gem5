#define main numeric_main
#include "guest.c"
#undef main
#include "negative.h"
const struct Input test_data[1] = {{0}};
const uint32_t test_count = 1;

static int unchanged(const uint8_t *expected)
{
    uint64_t flags, sat;
    __asm__ volatile("csrr %0, amefflags\n csrr %1, amexsat":"=r"(flags),"=r"(sat));
    collect(0,0,64);
    return !memcmp(result,expected,64) && flags==8 && sat==0;
}
int main(int argc, char **argv)
{
    if (argc<2) return 2;
    FILE *out=fopen(argv[1],"w");
    if (!out) return 3;
    __asm__ volatile("li t0,0x3c\n ame.acquire t1,t0":::"t0","t1","memory");
    __asm__ volatile("csrw mtvec,%0"::"r"(trap_handler):"memory");
    memset(poison,0xa5,64);
    struct Input in={0};
    for (unsigned n=0;n<sizeof(probes)/sizeof(probes[0]);++n) {
        setup(&in,0,0);
        traps=cause=trap_pc=trap_value=0;
        probes[n].run();
        int ok=traps==1 && cause==2 && trap_pc==(uintptr_t)probes[n].run &&
               trap_value==probes[n].word && unchanged(poison);
        fprintf(out,"negative %u %u %lu %lu %lx %lx\n",n,ok,traps,cause,trap_pc,trap_value);
    }
    for (unsigned op=0;op<10;++op) {
        for (unsigned denied=0;denied<2;++denied) {
            setup(&in,0,0);
            __asm__ volatile("ame.release":::"memory");
            if (!denied) {
                const uint64_t ms=3UL<<23;
                __asm__ volatile("csrc mstatus,%0"::"r"(ms):"memory");
            }
            traps=cause=trap_pc=trap_value=0;
            kernels[op][0]();
            int ok=traps==1 && cause==2 && trap_pc==(uintptr_t)kernels[op][0] &&
                   trap_value==*(const uint32_t *)(uintptr_t)kernels[op][0];
            if (!denied) {
                const uint64_t ms=1UL<<23;
                __asm__ volatile("csrs mstatus,%0"::"r"(ms):"memory");
            }
            /* Access-denied architectural reads are forbidden too. Reacquire
               only after checking the exact trap, and do not claim this reset
               observes the pre-acquire contents. */
            __asm__ volatile("li t0,0x3c\n ame.acquire t1,t0":::"t0","t1","memory");
            fprintf(out,"access %u %u %u %lu %lu %lx %lx\n",op,denied,ok,traps,cause,trap_pc,trap_value);
        }
    }
    fclose(out);
    return 0;
}
