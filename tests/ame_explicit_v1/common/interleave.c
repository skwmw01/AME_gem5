#define main numeric_main
#include "guest.c"
#undef main
#include "../xuantie_v06/encoding.h"
#include "../spec_v05a/encoding.h"
const struct Input test_data[1]={{0}};
const uint32_t test_count=1;
int main(int argc,char **argv)
{
    if(argc<2) return 2;
    FILE *out=fopen(argv[1],"w"); if(!out) return 3;
    __asm__ volatile("li t0,0x3c\n ame.acquire t1,t0":::"t0","t1","memory");
    __asm__ volatile("csrw mtvec,%0"::"r"(trap_handler):"memory");
    memset(poison,0xa5,64);
    int failures=0;
    for(unsigned trial=0;trial<100;++trial) {
        struct Input in={0};
        uint32_t a[16],b[16];
        for(unsigned n=0;n<16;++n) {
            a[n]=0x80000000U+trial*777777U+n*999999U;
            b[n]=0xffffffffU-trial*999999U-n*12345U;
        }
        memcpy(in.a,a,64);memcpy(in.b,b,64);
        for(unsigned order=0;order<2;++order) {
            setup(&in,0,trial%2);
            traps=0;
            if(order==0) {
                __asm__ volatile(".word %c0\n .word %c1\n madd.ew m12,m8,m9"
                    ::"i"(XT06_ADD_I32(8,0,4)),"i"(SP05A_ADD_I32(9,8,4)):"memory");
            } else {
                __asm__ volatile(".word %c0\n .word %c1\n madd.ew m12,m8,m9"
                    ::"i"(SP05A_ADD_I32(8,0,4)),"i"(XT06_ADD_I32(9,8,4)):"memory");
            }
            uint32_t observed[16];uint64_t flags;
            __asm__ volatile("mss.1r m12,%1\n csrr %0,amefflags":"=r"(flags):"r"(observed):"memory");
            int good=traps==0 && flags==8;
            for(unsigned n=0;n<16;++n) good &= observed[n]==a[n]*2+b[n]*3;
            failures+=!good;
            fprintf(out,"%u %u %u\n",trial,order,good);
        }
    }
    fclose(out);return failures?1:0;
}
