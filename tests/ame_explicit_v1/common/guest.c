#include <stdint.h>
#include <stdio.h>
#include <string.h>

struct Input { uint32_t op, size; uint8_t a[64], b[64], c[64]; };
extern const struct Input test_data[];
extern const uint32_t test_count;
extern int write_binary(FILE *, const void *, size_t);
struct Observation { uint64_t info[13]; uint8_t data[128]; };
static struct Observation observation;
#define DECLARE(n) extern void kernel_##n##_0(void); extern void kernel_##n##_1(void); \
 extern void kernel_##n##_2(void); extern void kernel_##n##_3(void);
DECLARE(0) DECLARE(1) DECLARE(2) DECLARE(3) DECLARE(4)
DECLARE(5) DECLARE(6) DECLARE(7) DECLARE(8) DECLARE(9)
#define ROW(n) {kernel_##n##_0,kernel_##n##_1,kernel_##n##_2,kernel_##n##_3}
static void (*const kernels[10][4])(void) = {
 ROW(0), ROW(1), ROW(2), ROW(3), ROW(4), ROW(5), ROW(6), ROW(7), ROW(8), ROW(9)};
volatile uint64_t traps, cause, trap_pc, trap_value;
extern void trap_handler(void);
static uint8_t result[128] __attribute__((aligned(64)));
static uint8_t poison[64] __attribute__((aligned(64)));

static void setup(const struct Input *in, unsigned variant, unsigned mode)
{
    static const uint32_t input_type[10] = {0x40000020,0x20300120,0x40000020,
        0x20,0x40000008,0x14300110,0x20300110,0x40000020,0x20300120,0x14300110};
    static const uint32_t output_type[10] = {0x40000020,0x20300120,0x40000020,
        0x20,0x40000020,0x20300120,0x20300120,0x20300120,0x40000020,0x20300120};
    uint64_t source_type = input_type[in->op], dest_type = output_type[in->op];
    if (mode) {
        source_type = source_type == 0x20 ? 0x20300120 : 0x20;
        dest_type = dest_type == 0x20 ? 0x20300120 : 0x20;
    }
    /* Configure first: setters may clear data. Whole-register loads ignore Md. */
    __asm__ volatile(
        "msettyp m0, %[type]\n msettyp m4, %[type]\n"
        "msettyp m8, %[dest]\n msettyp m9, %[dest]\n"
        "msettyp m30, %[dest]\n msettyp m31, %[dest]\n"
        "msettyp m12, %[dest]\n asettyp acc0, %[dest]\n"
        "mls.1r m12, %[c]\n mmov.a.m acc0, m12\n"
        "mls.1r m0, %[a]\n mls.1r m4, %[b]\n"
        "mls.1r m8, %[p]\n mls.1r m9, %[p]\n"
        "mls.1r m30, %[p]\n mls.1r m31, %[p]\n"
        "mls.1r m1, %[p]\n mls.1r m5, %[p]\n"
        "csrw amestype, %[type]\n csrw amefflags, %[flags]\n"
        "csrw amexsat, zero\n"
        :: [type]"r"(source_type), [dest]"r"(dest_type), [a]"r"(in->a),
           [b]"r"(in->b), [c]"r"(in->c), [p]"r"(poison), [flags]"r"(8UL)
        : "memory");
    (void)variant;
}

static void collect(unsigned op, unsigned variant, unsigned size)
{
    if (op >= 4 && op <= 6) {
        __asm__ volatile("mmov.m.a m12, acc0\n mss.1r m12, %0" ::"r"(result):"memory");
    } else {
        switch (variant) {
        case 0: __asm__ volatile("mss.1r m8, %0\n mss.1r m9, %1" ::"r"(result),"r"(result+64):"memory"); break;
        case 1: __asm__ volatile("mss.1r m0, %0\n mss.1r m1, %1" ::"r"(result),"r"(result+64):"memory"); break;
        case 2: __asm__ volatile("mss.1r m4, %0\n mss.1r m5, %1" ::"r"(result),"r"(result+64):"memory"); break;
        case 3: __asm__ volatile("mss.1r m30, %0\n mss.1r m31, %1" ::"r"(result),"r"(result+64):"memory"); break;
        }
    }
    (void)size;
}
int main(int argc, char **argv)
{
    if (argc < 2) return 2;
    FILE *out = fopen(argv[1], "w");
    if (!out) return 3;
    __asm__ volatile("li t0, 0x3c\n ame.acquire t1, t0" :::"t0","t1","memory");
    __asm__ volatile("csrw mtvec, %0" ::"r"(trap_handler):"memory");
    memset(poison, 0xa5, sizeof(poison));
    for (unsigned i = 0; i < test_count; ++i) {
        const struct Input *in = &test_data[i];
        /* Every instruction is tested with both descriptor modes and all FRMs.
           Rotate aliasing configurations; directed boundaries cover all four. */
        for (unsigned mode = 0; mode < 2; ++mode) {
            unsigned variant = i % 4;
#ifdef CHAIN_TEST
            variant = in->size == 128 ? 0 : 1;
#ifdef S05A_TEST
            if (in->op == 9) variant = 0;
#endif
#endif
            setup(in, variant, mode);
            uint64_t scalar = ((i%5) << 5) | 3;
            __asm__ volatile("csrw fcsr, %0" ::"r"(scalar):"memory");
            traps = cause = trap_pc = trap_value = 0;
            kernels[in->op][variant]();
            uint64_t scalar_result;
            __asm__ volatile("fmv.w.x ft0,%1\n fmv.w.x ft1,%2\n"
                "fadd.s ft2,ft0,ft1,dyn\n fmv.x.w %0,ft2"
                : "=r"(scalar_result) : "r"(0x3f800000UL), "r"(0x33800000UL)
                : "ft0","ft1","ft2","memory");
            uint64_t flags, fcsr, dtype, stype, sat, adtype;
            __asm__ volatile("csrr %0, amefflags\n csrr %1, fcsr\n"
                "mgettyp %2, m0\n csrr %3, amestype\n csrr %4, amexsat"
                :"=r"(flags),"=r"(fcsr),"=r"(dtype),"=r"(stype),"=r"(sat)::"memory");
            __asm__ volatile("agettyp %0, acc0":"=r"(adtype)::"memory");
            collect(in->op, variant, in->size);
            uint64_t metadata[13] = {i,mode,traps,cause,trap_pc,trap_value,
                flags,fcsr,dtype,stype,sat,scalar_result,adtype};
            memcpy(observation.info, metadata, sizeof(metadata));
            memset(observation.data, 0, sizeof(observation.data));
            memcpy(observation.data, result, in->size);
            if (write_binary(out, &observation, sizeof(observation)) != sizeof(observation))
                return 4;
        }
    }
    fclose(out);
    return 0;
}
