/* Generated from this suite's encoding.csv; raw experimental words. */
#ifndef AME_SP05A_ENCODING_H
#define AME_SP05A_ENCODING_H
#define SP05A_ADD_I32_MATCH 0x4000005bu
#define SP05A_ADD_I32_MASK 0xfe00707fu
#define SP05A_ADD_I32(rd, rs1, rs2) (SP05A_ADD_I32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define SP05A_ADD_F32_MATCH 0x4000105bu
#define SP05A_ADD_F32_MASK 0xfe00707fu
#define SP05A_ADD_F32(rd, rs1, rs2) (SP05A_ADD_F32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define SP05A_MAX_I32_MATCH 0x4200005bu
#define SP05A_MAX_I32_MASK 0xfe00707fu
#define SP05A_MAX_I32(rd, rs1, rs2) (SP05A_MAX_I32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define SP05A_MAX_U32_MATCH 0x4200105bu
#define SP05A_MAX_U32_MASK 0xfe00707fu
#define SP05A_MAX_U32(rd, rs1, rs2) (SP05A_MAX_U32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define SP05A_MAC_I8_I32_MATCH 0x4400005bu
#define SP05A_MAC_I8_I32_MASK 0xfe007e7fu
#define SP05A_MAC_I8_I32(rd, rs1, rs2) (SP05A_MAC_I8_I32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define SP05A_MAC_F16_F32_MATCH 0x4400105bu
#define SP05A_MAC_F16_F32_MASK 0xfe007e7fu
#define SP05A_MAC_F16_F32(rd, rs1, rs2) (SP05A_MAC_F16_F32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define SP05A_MAC_BF16_F32_MATCH 0x4400205bu
#define SP05A_MAC_BF16_F32_MASK 0xfe007e7fu
#define SP05A_MAC_BF16_F32(rd, rs1, rs2) (SP05A_MAC_BF16_F32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define SP05A_CVT_F32_I32_MATCH 0x4600005bu
#define SP05A_CVT_F32_I32_MASK 0xfff0707fu
#define SP05A_CVT_F32_I32(rd, rs1, rs2) (SP05A_CVT_F32_I32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define SP05A_CVT_I32_F32_MATCH 0x4600105bu
#define SP05A_CVT_I32_F32_MASK 0xfff0707fu
#define SP05A_CVT_I32_F32(rd, rs1, rs2) (SP05A_CVT_I32_F32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define SP05A_CVT_F32_F16_MATCH 0x4600205bu
#define SP05A_CVT_F32_F16_MASK 0xfff0707fu
#define SP05A_CVT_F32_F16(rd, rs1, rs2) (SP05A_CVT_F32_F16_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#endif
