/* Independent logical-layout gates outside all performance ROIs. */
#define main compare_main
#include "bench.c"
#undef main
int main(int argc,char **argv){
 if(argc<2)return 2;FILE *f=fopen(argv[1],"w");if(!f)return 3;
 __asm__ volatile("li t0,0x3c\n ame.acquire t1,t0":::"t0","t1","memory");
 __asm__ volatile("csrw mtvec,%0"::"r"(trap_handler):"memory");
 cfg=&cases[0];unsigned id=0;
 for(unsigned op=4;op<=6;++op){unsigned depth=op==4?16:8;
  for(unsigned i=0;i<4;++i)for(unsigned j=0;j<4;++j)for(unsigned k=0;k<depth;++k){
   int a[64]={0},b[64]={0};a[i*depth+k]=2;b[k*4+j]=-3;
   pack_tile(op,a,b,ta,tb);
   for(unsigned n=0;n<16;++n)tc[n]=op==4?n-8:fbits((float)((int)n-8));
   traps=0;configure(op,0);__asm__ volatile("csrw amefflags,zero":::"memory");
   load(op,0,ta,tb,tc,1);dispatch(op,0);store(op,0,output);
   uint64_t flags;__asm__ volatile("csrr %0,amefflags":"=r"(flags)::"memory");
   uint64_t h[6]={id++,op,i,j,k,traps|(flags<<32)};
   write_binary(f,h,sizeof(h));write_binary(f,output,64);
  }
 }
 // Every half bit pattern, then immediate use of the second output register.
 for(unsigned start=0;start<65536;start+=32){
  uint16_t h[32];for(unsigned i=0;i<32;++i)h[i]=start+i;pack_half(h,ta);
  traps=0;configure(9,0);uint64_t fp=0x20300120;
  __asm__ volatile("msettyp m8,%0\n msettyp m9,%0\n msettyp m10,%0\n csrw amefflags,zero"::"r"(fp):"memory");
  load(9,0,ta,tb,tc,0);compute_9_0();store(9,0,output);
  uint64_t conversion_flags;__asm__ volatile("csrr %0,amefflags":"=r"(conversion_flags)::"memory");
  __asm__ volatile("madd.ew m10,m9,m9\n mss.1r m10,%0"::"r"(output+32):"memory");
  uint64_t hd[6]={id++,9,start,0,0,traps|(conversion_flags<<32)};
  write_binary(f,hd,sizeof(hd));write_binary(f,output,192);
 }
 fclose(f);return 0;
}
