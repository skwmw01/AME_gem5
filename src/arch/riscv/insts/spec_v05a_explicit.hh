// Research explicit subset, not the native mtype-dependent ISA.
#ifndef __ARCH_RISCV_SPEC_V05A_EXPLICIT_HH__
#define __ARCH_RISCV_SPEC_V05A_EXPLICIT_HH__
#include "arch/riscv/insts/static_inst.hh"
#include "arch/riscv/regs/matrix.hh"
namespace gem5::RiscvISA
{
namespace S05A
{
enum class Element { SignedWord, UnsignedWord, Float, Byte, Half, BFloat };
enum class Cast { IntToFloat, FloatToInt, HalfToFloat };
uint32_t sum(MatRegContainer &, MatRegContainer, MatRegContainer, Element);
uint32_t max(MatRegContainer &, MatRegContainer, MatRegContainer, Element);
uint32_t multiplyAccumulate(MatRegContainer &, MatRegContainer,
                            MatRegContainer, Element);
uint32_t cast(MatRegContainer &, MatRegContainer, Cast);
uint32_t widenAll(MatRegContainer &, MatRegContainer &, MatRegContainer);
}
class S05AStaticInst : public RiscvStaticInst
{
  protected:
    S05AStaticInst(const char *name, ExtMachInst inst, OpClass op)
        : RiscvStaticInst(name, inst, op) {}
    std::string generateDisassembly(Addr, const loader::SymbolTable *) const
        override;
};
}
#endif
