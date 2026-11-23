/* Repeat short calls inside one ROI, retaining every call's cold preparation. */
#define measure batch_measure
#include "bench.c"
#undef measure
extern void measure(void (*)(void),uint64_t *);
static void (*batch_target)(void);
FN("kernel") static void batch_calls(void){
 unsigned count=cfg->repeat<1024?1024/cfg->repeat:1;
 for(unsigned i=0;i<count;++i)batch_target();
}
void batch_measure(void (*function)(void),uint64_t *counters){
 batch_target=function;measure(batch_calls,counters);
}
