#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "cases.h"
#include "ops.h"
#define FN(sec) __attribute__((noinline,section(".text." sec)))
#ifndef CONTROL
#define CONTROL 0
#endif
#define CAP 262144
static uint8_t input[CAP*3] __attribute__((section(".input"),aligned(64)));
static uint32_t output[CAP] __attribute__((section(".output"),aligned(64)));
static uint8_t scratch[CAP*8] __attribute__((section(".scratch"),aligned(64)));
static uint8_t ta[128] __attribute__((aligned(64))),tb[64] __attribute__((aligned(64)));
static uint32_t tc[16] __attribute__((aligned(64)));
static uint32_t sequence[1024];
static const struct Case *cfg;
static uint32_t rnd;
static uint32_t active_op;
volatile uint64_t traps,cause,trap_pc,trap_value;
extern void trap_handler(void);
extern void measure(void (*)(void),uint64_t *);
extern int write_binary(FILE *,const void *,size_t);
static int next(void){rnd ^= rnd<<13;rnd ^= rnd>>17;rnd ^= rnd<<5;return (int)(rnd%7)-3;}
static uint32_t fbits(float x){uint32_t u;memcpy(&u,&x,4);return u;}
static uint16_t hbits(int n,int bf){uint32_t u=fbits((float)n);if(bf)return u>>16;if(!n)return 0;uint16_t s=n<0?0x8000:0;unsigned v=n<0?-n:n;return s|(v==1?0x3c00:v==2?0x4000:0x4200);}
static uint16_t hhalf(int n){uint16_t h=hbits(n,0);return (h&0x7fff)? h-0x400:h;}
static const uint32_t stypes[10]={0x40000020,0x20300120,0x40000020,0x20,0x40000008,0x14300110,0x20300110,0x40000020,0x20300120,0x14300110};
static const uint32_t dtypes[10]={0x40000020,0x20300120,0x40000020,0x20,0x40000020,0x20300120,0x20300120,0x20300120,0x48000020,0x20300120};
FN("type") static void input_type(unsigned op,unsigned bank){
 uint64_t st=stypes[op],dt=dtypes[op];
 if(GROUP==0||CONTROL){
  if(bank){__asm__ volatile("msettyp m16,%0"::"r"(st):"memory");if(op<4||op>=7)__asm__ volatile("msettyp m24,%0"::"r"(dt):"memory");if(op<7)__asm__ volatile("msettyp m20,%0"::"r"(st):"memory");}
  else {__asm__ volatile("msettyp m0,%0"::"r"(st):"memory");if(op<4||op>=7)__asm__ volatile("msettyp m8,%0"::"r"(dt):"memory");if(op<7)__asm__ volatile("msettyp m4,%0"::"r"(st):"memory");}
 }
}
FN("type") static void configure(unsigned op,unsigned bank){
 input_type(op,bank);
 if(op>=4&&op<=6){uint64_t dt=dtypes[op];__asm__ volatile("msettyp m12,%0\n asettyp acc0,%0"::"r"(dt):"memory");}
}
FN("move") static void load(unsigned op,unsigned bank,const void *a,const void *b,const void *c,int acc){
 if(bank){__asm__ volatile("mls.1r m16,%0"::"r"(a):"memory");if(op<7)__asm__ volatile("mls.1r m20,%0"::"r"(b):"memory");}
 else {__asm__ volatile("mls.1r m0,%0"::"r"(a):"memory");if(op<7)__asm__ volatile("mls.1r m4,%0"::"r"(b):"memory");}
#if GROUP == 1 && !CONTROL
 if(op==9)__asm__ volatile("mls.1r m1,%0"::"r"((const uint8_t*)a+64):"memory");
#endif
 if(acc)__asm__ volatile("mls.1r m12,%0\n mmov.a.m acc0,m12"::"r"(c):"memory");
}
FN("move") static void store(unsigned op,unsigned bank,void *out){
 if(op>=4&&op<=6)__asm__ volatile("mmov.m.a m12,acc0\n mss.1r m12,%0"::"r"(out):"memory");
 else if(bank)__asm__ volatile("mss.1r m24,%0"::"r"(out):"memory");
 else __asm__ volatile("mss.1r m8,%0"::"r"(out):"memory");
 if(op==9)__asm__ volatile("mss.1r m9,%0"::"r"((uint8_t*)out+64):"memory");
}
FN("layout") static void pack_tile(unsigned op,const int *a,const int *b,uint8_t *pa,uint8_t *pb){
 unsigned k=op==4?16:8;
 for(unsigned i=0;i<4;++i)for(unsigned t=0;t<k;++t){
  unsigned n=GROUP==0?(t/4)*16+i*4+t%4:i*k+t;
  if(op==4)pa[n]=(uint8_t)a[i*k+t];else ((uint16_t*)pa)[n]=hbits(a[i*k+t],op==6);
 }
 for(unsigned t=0;t<k;++t)for(unsigned j=0;j<4;++j){
  unsigned n=GROUP==0?(t/4)*16+j*4+t%4:GROUP==1?j*k+t:t*4+j;
  if(op==4)pb[n]=(uint8_t)b[t*4+j];else ((uint16_t*)pb)[n]=hbits(b[t*4+j],op==6);
 }
}
FN("layout") static void pack_half(const uint16_t *h,uint8_t *p){
#if GROUP == 1
 for(unsigned t=0;t<2;++t)for(unsigned i=0;i<32;++i)((uint16_t*)p)[t*32+i]=(i%8<4)?h[t*16+(i/8)*4+i%8]:0;
#else
 memcpy(p,h,64);
#endif
}
static void make_tile(unsigned op,unsigned seed){
 int v[144];rnd=seed+1;for(unsigned i=0;i<144;++i)v[i]=next();
 memset(ta,0,sizeof(ta));memset(tb,0,sizeof(tb));
 if(op>=4&&op<=6){pack_tile(op,v,v+64,ta,tb);for(unsigned i=0;i<16;++i)tc[i]=op==4?(uint32_t)v[128+i]:fbits((float)v[128+i]);}
 else if(op==9){uint16_t h[32];for(unsigned i=0;i<32;++i)h[i]=hhalf(v[i]);pack_half(h,ta);}
 else for(unsigned i=0;i<16;++i){((uint32_t*)ta)[i]=(op==1||op==8)?fbits(v[i]*0.5f):(uint32_t)v[i];((uint32_t*)tb)[i]=op==1?fbits(v[16+i]*0.5f):(uint32_t)v[16+i];}
}
#define W1(OP) \
FN("kernel.w1_" #OP) static void w1_##OP(void){ \
 if(cfg->roi!=0){if((GROUP==0||CONTROL||(OP>=4&&OP<=6))&&(cfg->state==0||cfg->control))configure(OP,0);load(OP,0,ta,tb,tc,OP>=4&&OP<=6);} \
 repeat_##OP##_0(cfg->repeat); \
 if(cfg->roi!=0)store(OP,0,output); }
W1(0) W1(1) W1(2) W1(3) W1(4) W1(5) W1(6) W1(7) W1(8) W1(9)
static void (*const one[10])(void)={w1_0,w1_1,w1_2,w1_3,w1_4,w1_5,w1_6,w1_7,w1_8,w1_9};
FN("kernel") static void empty(void){}
static void dispatch(unsigned op,unsigned bank){switch(op){
#define D(N) case N:if(bank)compute_##N##_1();else compute_##N##_0();break;
D(0) D(1) D(2) D(3) D(4) D(5) D(6) D(7) D(8) D(9)
}}
static void batch_dispatch(unsigned op,unsigned bank,const void *a,const void *b,unsigned repeat){switch(op){
#define BD(N) case N:if(bank)mixed_##N##_1(a,b,repeat);else mixed_##N##_0(a,b,repeat);break;
BD(0) BD(1) BD(2) BD(3) BD(4) BD(5) BD(6) BD(7) BD(8) BD(9)
}}
FN("kernel") static void mixed(void){
 unsigned family=cfg->op;unsigned types=family==2?3:2;
 unsigned ops[3]={family==0?0:family==1?2:family==2?4:7,family==0?1:family==1?3:family==2?5:8,6};
 if(cfg->work==2&&family==2){ops[0]=5;ops[1]=6;types=2;}
 if(GROUP==0||family==2)configure(ops[0],0);
 if(cfg->regpolicy&&(GROUP==0||family==2))configure(ops[1],1);
 if(family==2)load(ops[0],0,scratch,scratch+128,tc,1);
 unsigned prev=cfg->regpolicy?ops[0]:99;
 for(unsigned block=0;block<cfg->repeat/cfg->batch;++block){
  unsigned t=sequence[block],op=ops[t],bank=cfg->regpolicy&&t==1;
  if(cfg->work==3&&family==2&&op!=prev){
   configure(op,0);
   __asm__ volatile("mls.1r m12,%0\n mmov.a.m acc0,m12"::"r"(scratch+1024+t*64):"memory");
  }
  if(GROUP==0&&cfg->regpolicy==0&&op!=prev)input_type(op,0);
  uint8_t *a=scratch+t*256,*b=a+128;
  batch_dispatch(op,bank,a,b,cfg->batch);
  store(op,bank,output+t*32);
  if(cfg->work==3&&family==2)memcpy(scratch+1024+t*64,output+t*32,64);
  prev=op;
 }
 (void)types;
}
FN("layout") static void pack_gemm(void){
 unsigned m=cfg->m,n=cfg->n,k=cfg->k,k0=cfg->op==4?16:8,w=cfg->op==4?1:2;
 unsigned mt=(m+3)/4,nt=(n+3)/4,kt=(k+k0-1)/k0;
 uint8_t *a=input,*b=a+m*k*w,*pa=scratch,*pb=pa+mt*kt*64;
 for(unsigned i=0;i<mt;++i)for(unsigned q=0;q<kt;++q)for(unsigned r=0;r<4;++r)for(unsigned t=0;t<k0;++t){
  unsigned dst=GROUP==0?(t/4)*16+r*4+t%4:r*k0+t;
  for(unsigned x=0;x<w;++x)pa[(i*kt+q)*64+dst*w+x]=(i*4+r<m&&q*k0+t<k)?a[((i*4+r)*k+q*k0+t)*w+x]:0;
 }
 for(unsigned j=0;j<nt;++j)for(unsigned q=0;q<kt;++q)for(unsigned t=0;t<k0;++t)for(unsigned c=0;c<4;++c){
  unsigned dst=GROUP==0?(t/4)*16+c*4+t%4:GROUP==1?c*k0+t:t*4+c;
  for(unsigned x=0;x<w;++x)pb[(j*kt+q)*64+dst*w+x]=(q*k0+t<k&&j*4+c<n)?b[((q*k0+t)*n+j*4+c)*w+x]:0;
 }
}
FN("layout") static void scatter(unsigned m,unsigned n,unsigned nt){
 uint32_t *tmp=(uint32_t*)(scratch+131072);
 for(unsigned i=0;i<m;++i)for(unsigned j=0;j<n;++j)tmp[i*n+j]=output[((i/4)*nt+j/4)*16+(i%4)*4+j%4];
 memcpy(output,tmp,m*n*4);
}
FN("kernel") static void gemm_kernel_4(void){
 unsigned op=4,m=cfg->m,n=cfg->n,k=cfg->k,k0=op==4?16:8;
 unsigned mt=(m+3)/4,nt=(n+3)/4,kt=(k+k0-1)/k0;
 if(cfg->roi==2)pack_gemm();
 configure(op,0);
 uint8_t *pa=scratch,*pb=pa+mt*kt*64;
 for(unsigned i=0;i<mt;++i)for(unsigned j=0;j<nt;++j){
  uint32_t *ci=(uint32_t*)(input+(m*k+k*n)*(cfg->op==4?1:2));
  for(unsigned r=0;r<4;++r)for(unsigned c=0;c<4;++c){uint32_t v=(i*4+r<m&&j*4+c<n)?ci[(i*4+r)*n+j*4+c]:0;tc[r*4+c]=v;}
  __asm__ volatile("mls.1r m12,%0\n mmov.a.m acc0,m12"::"r"(tc):"memory");
  gemm_4_0(pa+i*kt*64,pb+j*kt*64,kt);
  // Tile output is the packed-call output ABI; end-to-end also scatters.
  store(op,0,output+(i*nt+j)*16);
 }
 if(cfg->roi==2)scatter(m,n,nt);
}
FN("kernel") static void gemm_kernel_5(void){
 unsigned op=5,m=cfg->m,n=cfg->n,k=cfg->k,k0=op==4?16:8;
 unsigned mt=(m+3)/4,nt=(n+3)/4,kt=(k+k0-1)/k0;
 if(cfg->roi==2)pack_gemm();
 configure(op,0);
 uint8_t *pa=scratch,*pb=pa+mt*kt*64;
 for(unsigned i=0;i<mt;++i)for(unsigned j=0;j<nt;++j){
  uint32_t *ci=(uint32_t*)(input+(m*k+k*n)*(cfg->op==4?1:2));
  for(unsigned r=0;r<4;++r)for(unsigned c=0;c<4;++c){uint32_t v=(i*4+r<m&&j*4+c<n)?ci[(i*4+r)*n+j*4+c]:0;tc[r*4+c]=v;}
  __asm__ volatile("mls.1r m12,%0\n mmov.a.m acc0,m12"::"r"(tc):"memory");
  gemm_5_0(pa+i*kt*64,pb+j*kt*64,kt);
  // Tile output is the packed-call output ABI; end-to-end also scatters.
  store(op,0,output+(i*nt+j)*16);
 }
 if(cfg->roi==2)scatter(m,n,nt);
}
FN("kernel") static void gemm_kernel_6(void){
 unsigned op=6,m=cfg->m,n=cfg->n,k=cfg->k,k0=op==4?16:8;
 unsigned mt=(m+3)/4,nt=(n+3)/4,kt=(k+k0-1)/k0;
 if(cfg->roi==2)pack_gemm();
 configure(op,0);
 uint8_t *pa=scratch,*pb=pa+mt*kt*64;
 for(unsigned i=0;i<mt;++i)for(unsigned j=0;j<nt;++j){
  uint32_t *ci=(uint32_t*)(input+(m*k+k*n)*(cfg->op==4?1:2));
  for(unsigned r=0;r<4;++r)for(unsigned c=0;c<4;++c){uint32_t v=(i*4+r<m&&j*4+c<n)?ci[(i*4+r)*n+j*4+c]:0;tc[r*4+c]=v;}
  __asm__ volatile("mls.1r m12,%0\n mmov.a.m acc0,m12"::"r"(tc):"memory");
  gemm_6_0(pa+i*kt*64,pb+j*kt*64,kt);
  // Tile output is the packed-call output ABI; end-to-end also scatters.
  store(op,0,output+(i*nt+j)*16);
 }
 if(cfg->roi==2)scatter(m,n,nt);
}
FN("layout") static void pack_widen(void){uint16_t *h=(uint16_t*)input;unsigned stride=GROUP==1?128:64;for(unsigned i=0;i<cfg->n;i+=32)pack_half(h+i,scratch+(i/32)*stride);}
FN("kernel") static void widen(void){
 if(cfg->roi==2)pack_widen();if(GROUP==0)configure(9,0);unsigned stride=GROUP==1?128:64;
 for(unsigned i=0;i<cfg->n;i+=32){load(9,0,scratch+(i/32)*stride,tb,tc,0);compute_9_0();store(9,0,output+i);}
}
FN("kernel") static void pipeline(void){
 uint32_t *a=(uint32_t*)input,*b=a+cfg->n;
 if(GROUP==0){uint64_t si=0x40000020,fp=0x20300120,ri=0x48000020;
  if(cfg->op==0)__asm__ volatile("msettyp m0,%0\n msettyp m4,%0\n msettyp m8,%0\n msettyp m9,%0"::"r"(si):"memory");
  else __asm__ volatile("msettyp m0,%0\n msettyp m4,%1\n msettyp m8,%1\n msettyp m9,%2"::"r"(si),"r"(fp),"r"(ri):"memory");
 }
 for(unsigned i=0;i<cfg->n;i+=16){
  load(0,0,a+i,b+i,tc,0);
  if(cfg->op==0){compute_0_0();pipeline_max();}
  else {compute_7_0();pipeline_add();pipeline_convert();}
  __asm__ volatile("mss.1r m9,%0"::"r"(output+i):"memory");
 }
}
static void prepare(void){
 memset(output,0,(cfg->work==5||cfg->work==6?cfg->n:96)*4);traps=cause=trap_pc=trap_value=0;
 if(cfg->work==0||cfg->work==1){make_tile(cfg->op,cfg->seed);
  if(cfg->roi==1&&cfg->state==0){uint64_t wrong=0x20;__asm__ volatile("msettyp m0,%0\n msettyp m4,%0\n msettyp m8,%0\n asettyp acc0,%0"::"r"(wrong):"memory");}
  else configure(cfg->op,0);
  if(cfg->roi==0)load(cfg->op,0,ta,tb,tc,cfg->op>=4&&cfg->op<=6);}
 else if(cfg->work==2||cfg->work==3){
  unsigned types=cfg->op==2?3:2;unsigned ops[3]={cfg->op==0?0:cfg->op==1?2:cfg->op==2?4:7,cfg->op==0?1:cfg->op==1?3:cfg->op==2?5:8,6};
  // W2 has two types, including FP16/BF16 MAC; W3 MAC has three.
  if(cfg->work==2&&cfg->op==2){ops[0]=5;ops[1]=6;types=2;}
  for(unsigned t=0;t<types;++t){make_tile(ops[t],cfg->seed+t);memcpy(scratch+t*256,ta,128);memcpy(scratch+t*256+128,tb,64);if(cfg->regpolicy||t==0)configure(ops[t],t==1);}
  if(cfg->work==3&&cfg->op==2){for(unsigned t=0;t<types;++t){make_tile(ops[t],cfg->seed+t);memcpy(scratch+1024+t*64,tc,64);}}
  if(cfg->op==2){configure(5,0);__asm__ volatile("mls.1r m12,%0\n mmov.a.m acc0,m12"::"r"(tc):"memory");}
  unsigned blocks=cfg->repeat/cfg->batch;
  for(unsigned i=0;i<blocks;++i)sequence[i]=cfg->pattern==0?(i/(blocks/types))%types:i%types;
  if(cfg->pattern==2){rnd=cfg->seed+101;for(unsigned i=blocks-1;i>0;--i){next();unsigned j=rnd%(i+1),t=sequence[i];sequence[i]=sequence[j];sequence[j]=t;}}
 }else if(cfg->work==4){
  rnd=cfg->seed+1;unsigned count=cfg->m*cfg->k+cfg->k*cfg->n,w=cfg->op==4?1:2;
  for(unsigned i=0;i<count;++i){int v=next();if(w==1)input[i]=(uint8_t)v;else ((uint16_t*)input)[i]=hbits(v,cfg->op==6);}
  uint32_t *ci=(uint32_t*)(input+count*w);
  for(unsigned i=0;i<cfg->m*cfg->n;++i){int v=next();if(!cfg->c0)v=0;ci[i]=cfg->op==4?(uint32_t)v:fbits((float)v);}
  if(cfg->roi!=2)pack_gemm();
 }else if(cfg->work==5){rnd=cfg->seed+1;uint16_t *h=(uint16_t*)input;for(unsigned i=0;i<cfg->n;++i)h[i]=hhalf(next());if(cfg->roi!=2)pack_widen();}
 else if(cfg->work==6){rnd=cfg->seed+1;uint32_t *a=(uint32_t*)input,*b=a+cfg->n;for(unsigned i=0;i<cfg->n;++i)a[i]=(uint32_t)next();for(unsigned i=0;i<cfg->n;++i){int v=next();b[i]=cfg->op?fbits(v*0.5f):(uint32_t)v;}}
 __asm__ volatile("csrw amefflags,zero\n csrw amexsat,zero\n csrw fcsr,zero\n fence rw,rw\n .rept 1024\n nop\n .endr":::"memory");
}
static unsigned number(const char *s){unsigned n=0;while(*s>='0'&&*s<='9')n=n*10+*s++-'0';return n;}
int main(int argc,char **argv){
 if(argc<4)return 2;FILE *file=fopen(argv[1],"w");if(!file)return 3;
 __asm__ volatile("li t0,0x3c\n ame.acquire t1,t0":::"t0","t1","memory");
 __asm__ volatile("csrw mtvec,%0"::"r"(trap_handler):"memory");
 unsigned start=number(argv[2]),end=number(argv[3]);if(end>CASE_COUNT)return 5;
 for(unsigned id=start;id<end;++id){cfg=&cases[id];prepare();
  void(*fn)(void)=cfg->work==0?empty:cfg->work==1?one[cfg->op]:(cfg->work==2||cfg->work==3)?mixed:cfg->work==4?(cfg->op==4?gemm_kernel_4:cfg->op==5?gemm_kernel_5:gemm_kernel_6):cfg->work==5?widen:pipeline;
  uint64_t header[13]={0};measure(fn,header+3);
  if(cfg->work==1&&cfg->roi==0)store(cfg->op,0,output);
  unsigned size=cfg->work==4?(cfg->roi==2?cfg->m*cfg->n:((cfg->m+3)/4)*((cfg->n+3)/4)*16):cfg->work==5||cfg->work==6?cfg->n:(cfg->work==2||cfg->work==3)?96:cfg->op==9?32:16;
  uint64_t flags,fcsr,sat;
  __asm__ volatile("csrr %0,amefflags\n csrr %1,fcsr\n csrr %2,amexsat":"=r"(flags),"=r"(fcsr),"=r"(sat)::"memory");
  header[0]=id;header[1]=size;header[2]=traps;header[7]=flags;header[8]=fcsr;header[9]=sat;header[10]=cause;header[11]=trap_pc;header[12]=trap_value;
  write_binary(file,header,sizeof(header));write_binary(file,output,size*4);
 }
 fclose(file);return 0;
}
