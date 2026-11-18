#include <stdint.h>
#include <string.h>

#define ALIGNED __attribute__((aligned(64)))
#define CALLS 96
#define CONFIGS 49
static const unsigned repeats_list[] = {1, 2, 4, 8, 16, 64, 256};
static const unsigned groups[] = {1, 4, 16, 32};
static float af[64] ALIGNED, bf[64] ALIGNED;
static int32_t ai[64] ALIGNED, bi[64] ALIGNED;
static int8_t ab[64] ALIGNED, bb[64] ALIGNED;
static uint32_t output[16] ALIGNED;

struct record {
    uint64_t counters[2];
    uint64_t status;
    uint32_t output[16];
};
static struct record records[CONFIGS * CALLS];
_Static_assert(sizeof(struct record) == 88, "host binary record layout");
typedef void (*measure_fn)(const void *, const void *, void *, unsigned,
                           unsigned, uint64_t *);
extern void measure_specialized(const void *, const void *, void *, unsigned,
                                unsigned, uint64_t *);
extern void measure_shared(const void *, const void *, void *, unsigned,
                           unsigned, uint64_t *);
extern void batch_begin(void), batch_end(void);

/* The host independently generates this same logical row-major input, then
 * computes reference products without using the guest's packed layout. */
static uint32_t seed = 0x6a09e667;
static int next_value(void)
{
    seed = seed * 1664525u + 1013904223u;
    return (int)((seed >> 16) % 7) - 3;
}

static void pack(void)
{
    int32_t a[64], b[64];
    for (unsigned i = 0; i < 64; ++i) a[i] = next_value();
    for (unsigned i = 0; i < 64; ++i) b[i] = next_value();
    for (unsigned s = 0; s < 4; ++s)
        for (unsigned i = 0; i < 4; ++i)
            for (unsigned j = 0; j < 4; ++j) {
                unsigned p = s * 16 + i * 4 + j;
                int32_t av = a[i * 16 + s * 4 + j];
                int32_t bv = b[(s * 4 + i) * 4 + j];
                af[p] = (float)av; bf[p] = (float)bv;
                ai[p] = av; bi[p] = bv;
                ab[p] = (int8_t)av; bb[p] = (int8_t)bv;
            }
}

static unsigned kind_at(unsigned sequence, unsigned index)
{
    return sequence < 3 ? sequence : (index / groups[sequence - 3]) % 3;
}

static int equal(const char *a, const char *b)
{
    while (*a && *a == *b) { ++a; ++b; }
    return *a == *b;
}

/* Binary output avoids the shared runtime's 512 KiB formatted-file limit.
 * All I/O occurs after batch_end; ABI matches common/runtime.c. */
static long semi(long op, uintptr_t *args)
{
    register long a0 __asm__("a0") = op;
    register uintptr_t *a1 __asm__("a1") = args;
    __asm__ volatile("fence rw, rw\n\tslli zero, zero, 31\n\tebreak\n\t"
                     "srai zero, zero, 7\n\tfence rw, rw"
                     : "+r"(a0) : "r"(a1) : "memory");
    return a0;
}

static int write_records(const char *path, const uint64_t *header, unsigned n)
{
    unsigned length = 0;
    while (path[length]) ++length;
    uintptr_t open_args[] = {(uintptr_t)path, 5, length}; /* write binary */
    long fd = semi(1, open_args);
    if (fd <= 0) return 5;
    uintptr_t head_args[] = {(uintptr_t)fd, (uintptr_t)header, 8 * 8};
    uintptr_t data_args[] = {(uintptr_t)fd, (uintptr_t)records,
                             n * sizeof(records[0])};
    uintptr_t close_args[] = {(uintptr_t)fd};
    long h = semi(5, head_args);
    long d = semi(5, data_args);
    long c = semi(2, close_args);
    return h || d || c ? 6 : 0;
}

int main(int argc, char **argv)
{
    /* argv: report, specialized|shared, smoke|full */
    if (argc != 4) return 2;
    measure_fn measure;
    if (equal(argv[2], "specialized")) measure = measure_specialized;
    else if (equal(argv[2], "shared")) measure = measure_shared;
    else return 2;
    unsigned nr;
    if (equal(argv[3], "full")) nr = 7;
    else if (equal(argv[3], "smoke")) nr = 1;
    else return 2;
    const void *a[] = {af, ai, ab};
    const void *b[] = {bf, bi, bb};
    pack();
    uint64_t acquired, nlen, udsz, owned;
    __asm__ volatile("li t0, 0x3c\n\tame.acquire %0, t0\n\t"
                     "csrw amestatus, zero\n\tcsrr %1, amenlen\n\t"
                     "csrr %2, ameudsz\n\tcsrr %3, ameown"
                     : "=r"(acquired), "=r"(nlen), "=r"(udsz), "=r"(owned)
                     :: "t0", "memory");
    if (!(acquired & 1) || !owned || nlen != 4 || udsz != 32) return 3;
    batch_begin();
    unsigned index = 0;
    for (unsigned r = 0; r < nr; ++r)
        for (unsigned seq = 0; seq < 7; ++seq)
            for (unsigned call = 0; call < CALLS; ++call) {
                unsigned kind = kind_at(seq, call);
                unsigned repeats = repeats_list[r];
                if (kind > 2 || repeats < 1) return 4;
                struct record *record = &records[index++];
                /* Reuse the identical output address for every call. */
                for (unsigned i = 0; i < 16; ++i) output[i] = 0xdeadbeef;
                measure(a[kind], b[kind], output, kind, repeats,
                        record->counters);
                __asm__ volatile("csrr %0, amestatus" : "=r"(record->status));
                memcpy(record->output, output, sizeof(output));
            }
    batch_end();
    uint64_t final_status;
    __asm__ volatile("csrr %0, amestatus\n\tame.release" : "=r"(final_status)
                     :: "memory");
    uint64_t header[] = {0x5a54545049303601ULL, nr, index, acquired,
                         owned, nlen, udsz, final_status};
    int io_status = write_records(argv[1], header, index);
    return io_status ? io_status : final_status ? 7 : 0;
}
