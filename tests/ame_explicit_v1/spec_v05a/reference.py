"""S05A adapter: row-major rectangular B and full 32-element expansion."""
from common import ieee


def execute(mnemonic, left, right, initial):
    def elements(data, size):
        return [int.from_bytes(data[n:n+size], 'little') for n in range(0, 64, size)]
    status = 0
    output = []
    if '.mac.' in mnemonic:
        integer = '.i8.' in mnemonic
        a, b = elements(left, 1 if integer else 2), elements(right, 1 if integer else 2)
        output = elements(initial, 4)
        depth = 16 if integer else 8
        for index in range(16):
            row, column = divmod(index, 4)
            for inner in range(depth):
                lhs, rhs = a[row*depth+inner], b[inner*4+column]
                if integer:
                    lhs -= 256 if lhs >= 128 else 0
                    rhs -= 256 if rhs >= 128 else 0
                    output[index] = (output[index] + lhs*rhs) % 2**32
                else:
                    lhs, f1 = ieee.widen(lhs, mnemonic.endswith('bf16.f32'))
                    rhs, f2 = ieee.widen(rhs, mnemonic.endswith('bf16.f32'))
                    output[index], f3 = ieee.fma(lhs, rhs, output[index])
                    status |= f1 | f2 | f3
    elif mnemonic.endswith('cvt.f32.f16'):
        for raw in elements(left, 2):
            converted, raised = ieee.widen(raw)
            output.append(converted)
            status |= raised
    else:
        for lhs, rhs in zip(elements(left, 4), elements(right, 4)):
            raised = 0
            operation = mnemonic.split('.', 1)[1]
            if operation == 'add.i32':
                value = (lhs+rhs) % 2**32
            elif operation == 'add.f32':
                value, raised = ieee.add(lhs, rhs)
            elif operation == 'max.u32':
                value = lhs if lhs > rhs else rhs
            elif operation == 'max.i32':
                sl = lhs if lhs < 2**31 else lhs-2**32
                sr = rhs if rhs < 2**31 else rhs-2**32
                value = lhs if sl > sr else rhs
            elif operation == 'cvt.f32.i32':
                value, raised = ieee.int_to_float(lhs)
            elif operation == 'cvt.i32.f32':
                value, raised = ieee.float_to_int(lhs)
            else:
                raise ValueError(mnemonic)
            output.append(value)
            status |= raised
    return b''.join(n.to_bytes(4, 'little') for n in output), status
