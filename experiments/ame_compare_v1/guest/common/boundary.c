#define main compare_main
#include "bench.c"
#undef main
#if GROUP == 0
#define CVT 0xa2d0002b
#define MAC 0x9e40002b
#elif GROUP == 1
#define CVT 0x2600200b
#define MAC 0x2440000b
#else
#define CVT 0x4600205b
#define MAC 0x4440005b
#endif
int main(int argc,char **argv){
 if(argc<2)return 2;FILE *f=fopen(argv[1],"w");if(!f)return 3;cfg=&cases[0];
 __asm__ volatile("li t0,0x3c\n ame.acquire t1,t0":::"t0","t1","memory");
 __asm__ volatile("csrw mtvec,%0"::"r"(trap_handler):"memory");
 for(unsigned variant=0;variant<2;++variant){
  make_tile(9,0);configure(9,0);uint64_t fp=0x20300120;
  memset(output,0xa5,128);
  __asm__ volatile("msettyp m30,%0\n msettyp m31,%0\n mls.1r m30,%1\n mls.1r m31,%1"::"r"(fp),"r"(output):"memory");
  load(9,0,ta,tb,tc,0);traps=cause=trap_pc=trap_value=0;
  __asm__ volatile("csrw amefflags,zero":::"memory");
  if(variant==0)__asm__ volatile(".word %c0"::"i"(CVT|(30<<7)):"memory");
  else __asm__ volatile(".word %c0"::"i"(CVT|(31<<7)):"memory");
  __asm__ volatile("mss.1r m30,%0\n mss.1r m31,%1"::"r"(output),"r"(output+16):"memory");
  uint64_t flags;__asm__ volatile("csrr %0,amefflags":"=r"(flags)::"memory");
  uint64_t h[4]={variant,traps,cause,flags};write_binary(f,h,32);write_binary(f,output,128);
 }
 for(unsigned invalid=0;invalid<2;++invalid){
  make_tile(4,0);configure(4,0);uint64_t dt=0x40000020;
  __asm__ volatile("asettyp acc3,%0\n msettyp m12,%0\n mls.1r m12,%1\n mmov.a.m acc3,m12"::"r"(dt),"r"(tc):"memory");
  load(4,0,ta,tb,tc,0);traps=cause=0;
  if(!invalid)__asm__ volatile(".word %c0"::"i"(MAC|(3<<7)):"memory");
  else __asm__ volatile(".word %c0"::"i"(MAC|(4<<7)):"memory");
  __asm__ volatile("mmov.m.a m12,acc3\n mss.1r m12,%0"::"r"(output):"memory");
  uint64_t h[4]={invalid+2,traps,cause,0};write_binary(f,h,32);write_binary(f,output,64);
 }
 fclose(f);return 0;
}
