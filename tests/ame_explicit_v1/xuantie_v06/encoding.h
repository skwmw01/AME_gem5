/* Generated from this suite's encoding.csv; raw experimental words. */
#ifndef AME_XT06_ENCODING_H
#define AME_XT06_ENCODING_H
#define XT06_ADD_I32_MATCH 0x2000000bu
#define XT06_ADD_I32_MASK 0xfe00707fu
#define XT06_ADD_I32(rd, rs1, rs2) (XT06_ADD_I32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define XT06_ADD_F32_MATCH 0x2000100bu
#define XT06_ADD_F32_MASK 0xfe00707fu
#define XT06_ADD_F32(rd, rs1, rs2) (XT06_ADD_F32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define XT06_MAX_I32_MATCH 0x2200000bu
#define XT06_MAX_I32_MASK 0xfe00707fu
#define XT06_MAX_I32(rd, rs1, rs2) (XT06_MAX_I32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define XT06_MAX_U32_MATCH 0x2200100bu
#define XT06_MAX_U32_MASK 0xfe00707fu
#define XT06_MAX_U32(rd, rs1, rs2) (XT06_MAX_U32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define XT06_MACBT_I8_I32_MATCH 0x2400000bu
#define XT06_MACBT_I8_I32_MASK 0xfe007e7fu
#define XT06_MACBT_I8_I32(rd, rs1, rs2) (XT06_MACBT_I8_I32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define XT06_MACBT_F16_F32_MATCH 0x2400100bu
#define XT06_MACBT_F16_F32_MASK 0xfe007e7fu
#define XT06_MACBT_F16_F32(rd, rs1, rs2) (XT06_MACBT_F16_F32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define XT06_MACBT_BF16_F32_MATCH 0x2400200bu
#define XT06_MACBT_BF16_F32_MASK 0xfe007e7fu
#define XT06_MACBT_BF16_F32(rd, rs1, rs2) (XT06_MACBT_BF16_F32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define XT06_CVT_F32_I32_MATCH 0x2600000bu
#define XT06_CVT_F32_I32_MASK 0xfff0707fu
#define XT06_CVT_F32_I32(rd, rs1, rs2) (XT06_CVT_F32_I32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define XT06_CVT_I32_F32_MATCH 0x2600100bu
#define XT06_CVT_I32_F32_MASK 0xfff0707fu
#define XT06_CVT_I32_F32(rd, rs1, rs2) (XT06_CVT_I32_F32_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#define XT06_CVTLO_F32_F16_MATCH 0x2600200bu
#define XT06_CVTLO_F32_F16_MASK 0xfff0707fu
#define XT06_CVTLO_F32_F16(rd, rs1, rs2) (XT06_CVTLO_F32_F16_MATCH | ((rd) << 7) | ((rs1) << 15) | ((rs2) << 20))
#endif
