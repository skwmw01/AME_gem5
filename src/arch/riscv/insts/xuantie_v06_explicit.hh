// Research explicit subset; see tests/ame_explicit_v1/xuantie_v06.
#ifndef __ARCH_RISCV_XUANTIE_V06_EXPLICIT_HH__
#define __ARCH_RISCV_XUANTIE_V06_EXPLICIT_HH__
#include "arch/riscv/insts/static_inst.hh"
#include "arch/riscv/regs/matrix.hh"
namespace gem5::RiscvISA
{
namespace X06
{
enum class Type { I32, U32, F32, I8, F16, BF16 };
enum class Conversion { I32ToF32, F32ToI32, LowF16ToF32 };
uint32_t add(MatRegContainer &, MatRegContainer, MatRegContainer, Type);
uint32_t maximum(MatRegContainer &, MatRegContainer, MatRegContainer, Type);
uint32_t macbt(MatRegContainer &, MatRegContainer, MatRegContainer, Type);
uint32_t convert(MatRegContainer &, MatRegContainer, Conversion);
}
class X06StaticInst : public RiscvStaticInst
{
  protected:
    X06StaticInst(const char *name, ExtMachInst inst, OpClass op)
        : RiscvStaticInst(name, inst, op) {}
    std::string generateDisassembly(Addr, const loader::SymbolTable *) const
        override;
};
}
#endif
