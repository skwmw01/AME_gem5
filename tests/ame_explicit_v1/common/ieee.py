"""Exact scalar IEEE reference primitives, independent of gem5/SoftFloat.

Fractions and integers only. Matrix layout and instruction semantics live in
separate suite adapters. Flags are RISC-V NX=1 UF=2 OF=4 DZ=8 NV=16.
"""
from fractions import Fraction


def decode(raw, eb=8, fb=23):
    sign = raw >> (eb + fb)
    e, f = (raw >> fb) & ((1 << eb) - 1), raw & ((1 << fb) - 1)
    if e == (1 << eb) - 1:
        return ('snan' if not f & (1 << (fb-1)) else 'nan', sign, None) if f else ('inf', sign, None)
    bias = (1 << (eb-1)) - 1
    significand = f if e == 0 else (1 << fb) | f
    exponent = (e if e else 1) - bias - fb
    magnitude = Fraction(significand * (1 << max(exponent, 0)), 1 << max(-exponent, 0))
    return 'finite', sign, -magnitude if sign else magnitude


def nearest(value):
    q, r = divmod(value.numerator, value.denominator)
    return q + (2*r > value.denominator or (2*r == value.denominator and q & 1))


def round32(value, zero_sign=0):
    if not value:
        return zero_sign << 31, 0
    sign = int(value < 0)
    value = abs(value)
    exponent = value.numerator.bit_length() - value.denominator.bit_length()
    if value < Fraction(2) ** exponent:
        exponent -= 1
    step = Fraction(2) ** max(exponent-23, -149)
    significand = nearest(value / step)
    rounded = significand * step
    inexact = rounded != value
    if rounded >= Fraction(2) ** 128:
        return (sign << 31) | 0x7f800000, 5
    if rounded < Fraction(2) ** -126:
        return (sign << 31) | significand, (3 if inexact else 0)
    e = exponent
    if significand == 1 << 24:
        e += 1
        significand >>= 1
    e = max(e, -126)
    return (sign << 31) | ((e+127) << 23) | (significand & 0x7fffff), int(inexact)


def widen(raw, bf=False):
    kind, sign, value = decode(raw, 8 if bf else 5, 7 if bf else 10)
    if 'nan' in kind:
        return 0x7fc00000, 16 if kind == 'snan' else 0
    if kind == 'inf':
        return sign << 31 | 0x7f800000, 0
    return round32(value, sign)


def add(a, b):
    x, y = decode(a), decode(b)
    nv = 16 if 'snan' in (x[0], y[0]) else 0
    if any('nan' in z[0] for z in (x, y)):
        return 0x7fc00000, nv
    if x[0] == y[0] == 'inf' and x[1] != y[1]:
        return 0x7fc00000, 16
    if x[0] == 'inf' or y[0] == 'inf':
        return a if x[0] == 'inf' else b, 0
    return round32(x[2]+y[2], x[1] & y[1])


def fma(a, b, c):
    x, y, z = decode(a), decode(b), decode(c)
    invalid = (x[0] == 'inf' and y[2] == 0) or (y[0] == 'inf' and x[2] == 0)
    nv = 16 if invalid or 'snan' in (x[0], y[0], z[0]) else 0
    if invalid or any('nan' in q[0] for q in (x, y, z)):
        return 0x7fc00000, nv
    prod_sign = x[1] ^ y[1]
    if x[0] == 'inf' or y[0] == 'inf':
        if z[0] == 'inf' and z[1] != prod_sign:
            return 0x7fc00000, 16
        return prod_sign << 31 | 0x7f800000, 0
    if z[0] == 'inf':
        return c, 0
    return round32(x[2]*y[2]+z[2], prod_sign & z[1])


def int_to_float(raw):
    value = raw - (1 << 32) if raw >> 31 else raw
    return round32(Fraction(value))


def float_to_int(raw):
    kind, sign, value = decode(raw)
    if kind != 'finite':
        return (0x80000000 if kind == 'inf' and sign else 0x7fffffff), 16
    rounded = nearest(value)
    if rounded < -(1 << 31):
        return 0x80000000, 16
    if rounded >= 1 << 31:
        return 0x7fffffff, 16
    return rounded & 0xffffffff, int(rounded != value)
