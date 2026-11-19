"""X06 reference: four row dot products against B-transpose rows."""
import struct
from common import ieee


def execute(name, a, b, c):
    aw, bw = struct.unpack('<16I', a), struct.unpack('<16I', b)
    result, flags = [], 0
    if '.macbt.' in name:
        width = 1 if '.i8.' in name else 2
        av = struct.unpack('<64b' if width == 1 else '<32H', a)
        bv = struct.unpack('<64b' if width == 1 else '<32H', b)
        cv = struct.unpack('<16I', c)
        for i in range(4):
            for j in range(4):
                acc = cv[4*i+j]
                for k in range(16//width):
                    x, y = av[i*(16//width)+k], bv[j*(16//width)+k]
                    if width == 1:
                        acc = (acc+x*y) & 0xffffffff
                    else:
                        x, xf = ieee.widen(x, '.bf16.' in name)
                        y, yf = ieee.widen(y, '.bf16.' in name)
                        acc, af = ieee.fma(x, y, acc)
                        flags |= xf | yf | af
                result.append(acc)
    elif '.cvtlo.' in name:
        half = struct.unpack('<32H', a)
        for row in range(4):
            for col in range(4):
                value, f = ieee.widen(half[8*row+col])
                result.append(value)
                flags |= f
    else:
        for x, y in zip(aw, bw):
            f = 0
            if name.endswith('add.i32'):
                value = (x+y) & 0xffffffff
            elif name.endswith('add.f32'):
                value, f = ieee.add(x, y)
            elif name.endswith('max.i32'):
                value = x if (x ^ 0x80000000) >= (y ^ 0x80000000) else y
            elif name.endswith('max.u32'):
                value = max(x, y)
            elif name.endswith('cvt.f32.i32'):
                value, f = ieee.int_to_float(x)
            elif name.endswith('cvt.i32.f32'):
                value, f = ieee.float_to_int(x)
            else:
                raise ValueError(name)
            result.append(value)
            flags |= f
    return struct.pack('<16I', *result), flags
