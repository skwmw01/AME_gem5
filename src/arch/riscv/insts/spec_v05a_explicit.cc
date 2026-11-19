#include "arch/riscv/insts/spec_v05a_explicit.hh"
#include <array>
#include <cassert>
#include <softfloat.h>
namespace gem5::RiscvISA
{
std::string
S05AStaticInst::generateDisassembly(Addr, const loader::SymbolTable *) const
{
    const auto family = bits(machInst, 31, 25);
    std::string result = std::string(mnemonic) +
        (family == 0x22 ? " acc" : " m") +
        std::to_string(bits(machInst, 11, 7)) + ", m" +
        std::to_string(bits(machInst, 19, 15));
    if (family != 0x23)
        result += ", m" + std::to_string(bits(machInst, 24, 20));
    return result;
}
namespace S05A
{
namespace
{
struct FloatingState
{
    uint_fast8_t saved[3];
    FloatingState() : saved{softfloat_roundingMode, softfloat_detectTininess,
                            softfloat_exceptionFlags}
    {
        softfloat_roundingMode = softfloat_round_near_even;
        softfloat_detectTininess = softfloat_tininess_afterRounding;
        softfloat_exceptionFlags = 0;
    }
    ~FloatingState()
    {
        softfloat_roundingMode = saved[0];
        softfloat_detectTininess = saved[1];
        softfloat_exceptionFlags = saved[2];
    }
    unsigned raised() const { return softfloat_exceptionFlags & 0x1f; }
};
// Snapshot the complete 64-byte experimental source before any output store.
std::array<uint8_t, 64>
bytes(MatRegContainer &source)
{
    std::array<uint8_t, 64> data;
    auto rows = source.as<uint8_t>();
    for (size_t n = 0; n != data.size(); ++n)
        data[n] = rows[n/MaxMatRowLenInBytes][n%MaxMatRowLenInBytes];
    return data;
}
uint32_t word(const std::array<uint8_t, 64> &data, unsigned n)
{
    n *= 4;
    return uint32_t(data[n]) | uint32_t(data[n+1]) << 8 |
           uint32_t(data[n+2]) << 16 | uint32_t(data[n+3]) << 24;
}
uint16_t half(const std::array<uint8_t, 64> &data, unsigned n)
{
    return data[n*2] | uint16_t(data[n*2+1]) << 8;
}
void store(MatRegContainer &target, const std::array<uint32_t, 16> &values)
{
    auto rows = target.as<uint8_t>();
    for (unsigned n = 0; n != 64; ++n)
        rows[n/MaxMatRowLenInBytes][n%MaxMatRowLenInBytes] =
            values[n/4] >> ((n%4)*8);
}
bool isNan(uint32_t value)
{
    return (value & 0x7f800000) == 0x7f800000 && (value & 0x7fffff);
}
uint32_t resultBits(float32_t value)
{
    return isNan(value.v) ? 0x7fc00000 : value.v;
}
float32_t expand(uint16_t value, Element element)
{
    if (element == Element::Half)
        return {resultBits(f16_to_f32({value}))};
    const uint32_t raw = uint32_t(value) << 16;
    if (isNan(raw)) {
        if ((value & 0x40) == 0)
            softfloat_exceptionFlags |= softfloat_flag_invalid;
        return {0x7fc00000};
    }
    return {raw};
}
int32_t byteSigned(uint8_t n) { return n & 128 ? int32_t(n)-256 : n; }
int64_t wordSigned(uint32_t n)
{
    return n >> 31 ? -(int64_t(0x100000000ULL)-n) : int64_t(n);
}
uint32_t integerResult(uint32_t input)
{
    const auto accumulated = softfloat_exceptionFlags;
    softfloat_exceptionFlags = 0;
    uint32_t output = f32_to_i32({input}, softfloat_round_near_even, true);
    auto raised = softfloat_exceptionFlags;
    if (raised & softfloat_flag_invalid) {
        output = (input >> 31) && !isNan(input) ? 0x80000000 : 0x7fffffff;
        raised = softfloat_flag_invalid;
    }
    softfloat_exceptionFlags = accumulated | raised;
    return output;
}
}
uint32_t
sum(MatRegContainer &target, MatRegContainer left, MatRegContainer right,
    Element element)
{
    assert(element == Element::SignedWord || element == Element::Float);
    FloatingState state;
    const auto a = bytes(left), b = bytes(right);
    std::array<uint32_t, 16> result;
    for (unsigned n = 0; n != result.size(); ++n) {
        if (element == Element::Float)
            result[n] = resultBits(f32_add({word(a, n)}, {word(b, n)}));
        else
            result[n] = word(a, n) + word(b, n);
    }
    store(target, result);
    return state.raised();
}
uint32_t
max(MatRegContainer &target, MatRegContainer left, MatRegContainer right,
    Element element)
{
    assert(element == Element::SignedWord || element == Element::UnsignedWord);
    const auto a = bytes(left), b = bytes(right);
    std::array<uint32_t, 16> result;
    for (unsigned n = 0; n != result.size(); ++n) {
        uint32_t x = word(a, n), y = word(b, n);
        if (element == Element::UnsignedWord)
            result[n] = x < y ? y : x;
        else
            result[n] = wordSigned(x) < wordSigned(y) ? y : x;
    }
    store(target, result);
    return 0;
}
uint32_t
multiplyAccumulate(MatRegContainer &target, MatRegContainer left,
                   MatRegContainer right, Element element)
{
    assert(element == Element::Byte || element == Element::Half ||
           element == Element::BFloat);
    FloatingState state;
    const auto a = bytes(left), b = bytes(right), c = bytes(target);
    std::array<uint32_t, 16> result;
    for (unsigned out = 0; out != 16; ++out) {
        uint32_t value = word(c, out);
        unsigned row = out/4, column = out%4;
        if (element == Element::Byte) {
            for (unsigned k = 0; k != 16; ++k)
                value += uint32_t(byteSigned(a[row*16+k]) *
                                  byteSigned(b[k*4+column]));
        } else {
            for (unsigned k = 0; k != 8; ++k) {
                const auto lhs = expand(half(a, row*8+k), element);
                const auto rhs = expand(half(b, k*4+column), element);
                value = resultBits(f32_mulAdd(lhs, rhs, {value}));
            }
        }
        result[out] = value;
    }
    store(target, result);
    return state.raised();
}
uint32_t
cast(MatRegContainer &target, MatRegContainer source, Cast operation)
{
    assert(operation == Cast::IntToFloat || operation == Cast::FloatToInt);
    FloatingState state;
    const auto data = bytes(source);
    std::array<uint32_t, 16> converted;
    for (unsigned n = 0; n != converted.size(); ++n) {
        const auto raw = word(data, n);
        converted[n] = operation == Cast::IntToFloat ?
            resultBits(i32_to_f32(wordSigned(raw))) : integerResult(raw);
    }
    store(target, converted);
    return state.raised();
}
uint32_t
widenAll(MatRegContainer &first, MatRegContainer &second,
         MatRegContainer source)
{
    FloatingState state;
    const auto data = bytes(source);
    std::array<uint32_t, 16> low, high;
    for (unsigned n = 0; n != 32; ++n) {
        uint32_t value = expand(half(data, n), Element::Half).v;
        (n < 16 ? low : high)[n%16] = value;
    }
    // Both destinations have been validated before obtaining writable operands.
    store(first, low);
    store(second, high);
    return state.raised();
}
}
}
