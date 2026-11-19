#include "arch/riscv/insts/xuantie_v06_explicit.hh"
#include <algorithm>
#include <cassert>
#include <softfloat.h>
namespace gem5::RiscvISA
{
std::string
X06StaticInst::generateDisassembly(Addr, const loader::SymbolTable *) const
{
    std::string text(mnemonic);
    text += (bits(machInst, 31, 25) == 0x12 ? " acc" : " m");
    text += std::to_string(bits(machInst, 11, 7));
    text += ", m" + std::to_string(bits(machInst, 19, 15));
    if (bits(machInst, 31, 25) != 0x13)
        text += ", m" + std::to_string(bits(machInst, 24, 20));
    return text;
}
namespace X06
{
namespace
{
// This environment belongs to X06 alone. No architectural scalar fcsr access.
class Environment
{
    const uint_fast8_t rounding = softfloat_roundingMode;
    const uint_fast8_t tininess = softfloat_detectTininess;
    const uint_fast8_t exceptions = softfloat_exceptionFlags;
  public:
    Environment()
    {
        softfloat_roundingMode = softfloat_round_near_even;
        softfloat_detectTininess = softfloat_tininess_afterRounding;
        softfloat_exceptionFlags = 0;
    }
    ~Environment()
    {
        softfloat_roundingMode = rounding;
        softfloat_detectTininess = tininess;
        softfloat_exceptionFlags = exceptions;
    }
    uint32_t flags() const { return softfloat_exceptionFlags & 31; }
};
uint32_t
read(MatRegContainer &reg, unsigned byte, unsigned width)
{
    auto rows = reg.as<uint8_t>();
    uint32_t value = 0;
    for (unsigned i = 0; i < width; ++i)
        value |= uint32_t(rows[(byte+i)/MaxMatRowLenInBytes]
                              [(byte+i)%MaxMatRowLenInBytes]) << (8*i);
    return value;
}
void
write(MatRegContainer &reg, unsigned index, uint32_t value)
{
    auto rows = reg.as<uint8_t>();
    for (unsigned i = 0; i < 4; ++i) {
        unsigned byte = index*4+i;
        rows[byte/MaxMatRowLenInBytes][byte%MaxMatRowLenInBytes] =
            value >> (8*i);
    }
}
bool nan(uint32_t v) { return (v & 0x7fffffffU) > 0x7f800000U; }
uint32_t canonical(uint32_t v) { return nan(v) ? 0x7fc00000U : v; }
float32_t
widen(uint16_t v, Type type)
{
    if (type == Type::F16)
        return {canonical(f16_to_f32(float16_t{v}).v)};
    uint32_t bits = uint32_t(v) << 16;
    if (nan(bits) && !(bits & 0x400000))
        softfloat_exceptionFlags |= softfloat_flag_invalid;
    return {canonical(bits)};
}
int64_t signed32(uint32_t v)
{
    return (v & 0x80000000U) ? int64_t(v) - 0x100000000LL : v;
}
uint32_t
toInteger(uint32_t raw)
{
    // Capture this element's exceptions separately: invalid has NV, no NX.
    auto previous = softfloat_exceptionFlags;
    softfloat_exceptionFlags = 0;
    uint32_t value = f32_to_i32({raw}, softfloat_round_near_even, true);
    if (softfloat_exceptionFlags & softfloat_flag_invalid) {
        value = !nan(raw) && (raw >> 31) ? 0x80000000U : 0x7fffffffU;
        softfloat_exceptionFlags = softfloat_flag_invalid;
    }
    softfloat_exceptionFlags |= previous;
    return value;
}
}
uint32_t
add(MatRegContainer &dst, MatRegContainer a, MatRegContainer b, Type type)
{
    assert(type == Type::I32 || type == Type::F32);
    Environment env;
    auto result = dst;
    for (unsigned i = 0; i < 16; ++i) {
        auto x = read(a, i*4, 4), y = read(b, i*4, 4);
        auto z = type == Type::I32 ? x+y : canonical(f32_add({x}, {y}).v);
        write(result, i, z);
    }
    dst = result;
    return env.flags();
}
uint32_t
maximum(MatRegContainer &dst, MatRegContainer a, MatRegContainer b,
        Type type)
{
    assert(type == Type::I32 || type == Type::U32);
    auto result = dst;
    for (unsigned i = 0; i < 16; ++i) {
        uint32_t x = read(a, i*4, 4), y = read(b, i*4, 4);
        bool takeA = type == Type::I32 ? signed32(x) >= signed32(y) : x >= y;
        write(result, i, takeA ? x : y);
    }
    dst = result;
    return 0;
}
uint32_t
macbt(MatRegContainer &dst, MatRegContainer a, MatRegContainer bt, Type type)
{
    assert(type == Type::I8 || type == Type::F16 || type == Type::BF16);
    Environment env;
    auto result = dst;
    const unsigned depth = type == Type::I8 ? 16 : 8;
    for (unsigned row = 0; row < 4; ++row) {
        for (unsigned col = 0; col < 4; ++col) {
            uint32_t sum = read(dst, (row*4+col)*4, 4);
            for (unsigned k = 0; k < depth; ++k) {
                if (type == Type::I8) {
                    int x = read(a, row*16+k, 1);
                    int y = read(bt, col*16+k, 1);
                    x = x < 128 ? x : x-256;
                    y = y < 128 ? y : y-256;
                    sum += uint32_t(x*y);
                } else {
                    auto x = widen(read(a, (row*8+k)*2, 2), type);
                    auto y = widen(read(bt, (col*8+k)*2, 2), type);
                    sum = canonical(f32_mulAdd(x, y, {sum}).v);
                }
            }
            write(result, row*4+col, sum);
        }
    }
    dst = result;
    return env.flags();
}
uint32_t
convert(MatRegContainer &dst, MatRegContainer src, Conversion conversion)
{
    Environment env;
    auto result = dst;
    for (unsigned i = 0; i < 16; ++i) {
        uint32_t value;
        switch (conversion) {
          case Conversion::I32ToF32:
            value = canonical(i32_to_f32(signed32(read(src, i*4, 4))).v);
            break;
          case Conversion::F32ToI32:
            value = toInteger(read(src, i*4, 4));
            break;
          case Conversion::LowF16ToF32:
            // Four rows of eight half elements; only columns 0..3.
            value = widen(read(src, ((i/4)*8+i%4)*2, 2), Type::F16).v;
            break;
          default: panic("invalid X06 conversion");
        }
        write(result, i, value);
    }
    dst = result;
    return env.flags();
}
}
}
