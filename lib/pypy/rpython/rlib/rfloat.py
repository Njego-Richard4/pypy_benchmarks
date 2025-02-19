"""Float constants"""

import math, struct

from rpython.annotator.model import SomeString, SomeChar
from rpython.rlib import objectmodel, unroll
from rpython.rtyper.extfunc import register_external
from rpython.rtyper.tool import rffi_platform
from rpython.translator.tool.cbuild import ExternalCompilationInfo


USE_SHORT_FLOAT_REPR = True # XXX make it a translation option?

class CConfig:
    _compilation_info_ = ExternalCompilationInfo(includes=["float.h"])

float_constants = ["DBL_MAX", "DBL_MIN", "DBL_EPSILON"]
int_constants = ["DBL_MAX_EXP", "DBL_MAX_10_EXP",
                 "DBL_MIN_EXP", "DBL_MIN_10_EXP",
                 "DBL_DIG", "DBL_MANT_DIG",
                 "FLT_RADIX", "FLT_ROUNDS"]
for const in float_constants:
    setattr(CConfig, const, rffi_platform.DefinedConstantDouble(const))
for const in int_constants:
    setattr(CConfig, const, rffi_platform.DefinedConstantInteger(const))
del float_constants, int_constants, const

globals().update(rffi_platform.configure(CConfig))

def rstring_to_float(s):
    return rstring_to_float_impl(s)

def rstring_to_float_impl(s):
    if USE_SHORT_FLOAT_REPR:
        from rpython.rlib.rdtoa import strtod
        return strtod(s)
    sign, before_point, after_point, exponent = break_up_float(s)
    if not before_point and not after_point:
        raise ValueError
    return parts_to_float(sign, before_point, after_point, exponent)

def oo_rstring_to_float(s):
    from rpython.rtyper.annlowlevel import oostr
    from rpython.rtyper.ootypesystem import ootype
    lls = oostr(s)
    return ootype.ooparse_float(lls)

register_external(rstring_to_float, [SomeString(can_be_None=False)], float,
                  llimpl=rstring_to_float_impl,
                  ooimpl=oo_rstring_to_float,
                  sandboxsafe=True)


# float as string  -> sign, beforept, afterpt, exponent
def break_up_float(s):
    i = 0

    sign = ''
    before_point = ''
    after_point = ''
    exponent = ''

    if s[i] in '+-':
        sign = s[i]
        i += 1

    while i < len(s) and s[i] in '0123456789':
        before_point += s[i]
        i += 1

    if i == len(s):
        return sign, before_point, after_point, exponent

    if s[i] == '.':
        i += 1
        while i < len(s) and s[i] in '0123456789':
            after_point += s[i]
            i += 1

        if i == len(s):
            return sign, before_point, after_point, exponent

    if s[i] not in  'eE':
        raise ValueError

    i += 1
    if i == len(s):
        raise ValueError

    if s[i] in '-+':
        exponent += s[i]
        i += 1

    if i == len(s):
        raise ValueError

    while i < len(s) and s[i] in '0123456789':
        exponent += s[i]
        i += 1

    if i != len(s):
        raise ValueError

    return sign, before_point, after_point, exponent

# string -> float helper

def parts_to_float(sign, beforept, afterpt, exponent):
    "NOT_RPYTHON"
    if not exponent:
        exponent = '0'
    return float("%s%s.%se%s" % (sign, beforept, afterpt, exponent))

# float -> string

DTSF_STR_PRECISION = 12

DTSF_SIGN      = 0x1
DTSF_ADD_DOT_0 = 0x2
DTSF_ALT       = 0x4

DIST_FINITE   = 1
DIST_NAN      = 2
DIST_INFINITY = 3

# Equivalent to CPython's PyOS_double_to_string
def _formatd(x, code, precision, flags):
    "NOT_RPYTHON"
    if flags & DTSF_ALT:
        alt = '#'
    else:
        alt = ''

    if code == 'r':
        fmt = "%r"
    else:
        fmt = "%%%s.%d%s" % (alt, precision, code)
    s = fmt % (x,)

    if flags & DTSF_ADD_DOT_0:
        # We want float numbers to be recognizable as such,
        # i.e., they should contain a decimal point or an exponent.
        # However, %g may print the number as an integer;
        # in such cases, we append ".0" to the string.
        for c in s:
            if c in '.eE':
                break
        else:
            s += '.0'
    elif code == 'r' and s.endswith('.0'):
        s = s[:-2]

    return s

@objectmodel.enforceargs(float, SomeChar(), int, int)
def formatd(x, code, precision, flags=0):
    if USE_SHORT_FLOAT_REPR:
        from rpython.rlib.rdtoa import dtoa_formatd
        return dtoa_formatd(x, code, precision, flags)
    else:
        return _formatd(x, code, precision, flags)

def double_to_string(value, tp, precision, flags):
    if isfinite(value):
        special = DIST_FINITE
    elif isinf(value):
        special = DIST_INFINITY
    else:  #isnan(value):
        special = DIST_NAN
    result = formatd(value, tp, precision, flags)
    return result, special

def round_double(value, ndigits, half_even=False):
    """Round a float half away from zero.

    Specify half_even=True to round half even instead.
    """
    if USE_SHORT_FLOAT_REPR:
        return round_double_short_repr(value, ndigits, half_even)
    else:
        return round_double_fallback_repr(value, ndigits, half_even)

def round_double_short_repr(value, ndigits, half_even):
    # The basic idea is very simple: convert and round the double to
    # a decimal string using _Py_dg_dtoa, then convert that decimal
    # string back to a double with _Py_dg_strtod.  There's one minor
    # difficulty: Python 2.x expects round to do
    # round-half-away-from-zero, while _Py_dg_dtoa does
    # round-half-to-even.  So we need some way to detect and correct
    # the halfway cases.

    # a halfway value has the form k * 0.5 * 10**-ndigits for some
    # odd integer k.  Or in other words, a rational number x is
    # exactly halfway between two multiples of 10**-ndigits if its
    # 2-valuation is exactly -ndigits-1 and its 5-valuation is at
    # least -ndigits.  For ndigits >= 0 the latter condition is
    # automatically satisfied for a binary float x, since any such
    # float has nonnegative 5-valuation.  For 0 > ndigits >= -22, x
    # needs to be an integral multiple of 5**-ndigits; we can check
    # this using fmod.  For -22 > ndigits, there are no halfway
    # cases: 5**23 takes 54 bits to represent exactly, so any odd
    # multiple of 0.5 * 10**n for n >= 23 takes at least 54 bits of
    # precision to represent exactly.

    sign = copysign(1.0, value)
    value = abs(value)

    # find 2-valuation value
    m, expo = math.frexp(value)
    while m != math.floor(m):
        m *= 2.0
        expo -= 1

    # determine whether this is a halfway case.
    halfway_case = 0
    if not half_even and expo == -ndigits - 1:
        if ndigits >= 0:
            halfway_case = 1
        elif ndigits >= -22:
            # 22 is the largest k such that 5**k is exactly
            # representable as a double
            five_pow = 1.0
            for i in range(-ndigits):
                five_pow *= 5.0
            if math.fmod(value, five_pow) == 0.0:
                halfway_case = 1

    # round to a decimal string; use an extra place for halfway case
    strvalue = formatd(value, 'f', ndigits + halfway_case)

    if not half_even and halfway_case:
        buf = [c for c in strvalue]
        if ndigits >= 0:
            endpos = len(buf) - 1
        else:
            endpos = len(buf) + ndigits
        # Sanity checks: there should be exactly ndigits+1 places
        # following the decimal point, and the last digit in the
        # buffer should be a '5'
        if not objectmodel.we_are_translated():
            assert buf[endpos] == '5'
            if '.' in buf:
                assert endpos == len(buf) - 1
                assert buf.index('.') == len(buf) - ndigits - 2

        # increment and shift right at the same time
        i = endpos - 1
        carry = 1
        while i >= 0:
            digit = ord(buf[i])
            if digit == ord('.'):
                buf[i+1] = chr(digit)
                i -= 1
                digit = ord(buf[i])

            carry += digit - ord('0')
            buf[i+1] = chr(carry % 10 + ord('0'))
            carry /= 10
            i -= 1
        buf[0] = chr(carry + ord('0'))
        if ndigits < 0:
            buf.append('0')

        strvalue = ''.join(buf)

    return sign * rstring_to_float(strvalue)

# fallback version, to be used when correctly rounded
# binary<->decimal conversions aren't available
def round_double_fallback_repr(value, ndigits, half_even):
    if ndigits >= 0:
        if ndigits > 22:
            # pow1 and pow2 are each safe from overflow, but
            # pow1*pow2 ~= pow(10.0, ndigits) might overflow
            pow1 = math.pow(10.0, ndigits - 22)
            pow2 = 1e22
        else:
            pow1 = math.pow(10.0, ndigits)
            pow2 = 1.0

        y = (value * pow1) * pow2
        # if y overflows, then rounded value is exactly x
        if isinf(y):
            return value

    else:
        pow1 = math.pow(10.0, -ndigits);
        pow2 = 1.0 # unused; for translation
        y = value / pow1

    if half_even:
        z = round_away(y)
        if math.fabs(y - z) == 0.5:
            z = 2.0 * round_away(y / 2.0)
    else:
        if y >= 0.0:
            z = math.floor(y + 0.5)
        else:
            z = math.ceil(y - 0.5)
        if math.fabs(y - z) == 1.0:   # obscure case, see the test
            z = y

    if ndigits >= 0:
        z = (z / pow2) / pow1
    else:
        z *= pow1
    return z

INFINITY = 1e200 * 1e200
NAN = abs(INFINITY / INFINITY)    # bah, INF/INF gives us -NAN?

try:
    # Try to get math functions added in 2.6.
    from math import isinf, isnan, copysign, acosh, asinh, atanh, log1p
except ImportError:
    def isinf(x):
        "NOT_RPYTHON"
        return x == INFINITY or x == -INFINITY

    def isnan(v):
        "NOT_RPYTHON"
        return v != v

    def copysign(x, y):
        """NOT_RPYTHON. Return x with the sign of y"""
        if x < 0.:
            x = -x
        if y > 0. or (y == 0. and math.atan2(y, -1.) > 0.):
            return x
        else:
            return -x

    _2_to_m28 = 3.7252902984619141E-09; # 2**-28
    _2_to_p28 = 268435456.0; # 2**28
    _ln2 = 6.93147180559945286227E-01

    def acosh(x):
        "NOT_RPYTHON"
        if isnan(x):
            return NAN
        if x < 1.:
            raise ValueError("math domain error")
        if x >= _2_to_p28:
            if isinf(x):
                return x
            else:
                return math.log(x) + _ln2
        if x == 1.:
            return 0.
        if x >= 2.:
            t = x * x
            return math.log(2. * x - 1. / (x + math.sqrt(t - 1.0)))
        t = x - 1.0
        return log1p(t + math.sqrt(2. * t + t * t))

    def asinh(x):
        "NOT_RPYTHON"
        absx = abs(x)
        if not isfinite(x):
            return x
        if absx < _2_to_m28:
            return x
        if absx > _2_to_p28:
            w = math.log(absx) + _ln2
        elif absx > 2.:
            w = math.log(2. * absx + 1. / (math.sqrt(x * x + 1.) + absx))
        else:
            t = x * x
            w = log1p(absx + t / (1. + math.sqrt(1. + t)))
        return copysign(w, x)

    def atanh(x):
        "NOT_RPYTHON"
        if isnan(x):
            return x
        absx = abs(x)
        if absx >= 1.:
            raise ValueError("math domain error")
        if absx < _2_to_m28:
            return x
        if absx < .5:
            t = absx + absx
            t = .5 * log1p(t + t * absx / (1. - absx))
        else:
            t = .5 * log1p((absx + absx) / (1. - absx))
        return copysign(t, x)

    def log1p(x):
        "NOT_RPYTHON"
        if abs(x) < DBL_EPSILON // 2.:
            return x
        elif -.5 <= x <= 1.:
            y = 1. + x
            return math.log(y) - ((y - 1.) - x) / y
        else:
            return math.log(1. + x)

try:
    from math import expm1 # Added in Python 2.7.
except ImportError:
    def expm1(x):
        "NOT_RPYTHON"
        if abs(x) < .7:
            u = math.exp(x)
            if u == 1.:
                return x
            return (u - 1.) * x / math.log(u)
        return math.exp(x) - 1.

def round_away(x):
    # round() from libm, which is not available on all platforms!
    absx = abs(x)
    if absx - math.floor(absx) >= .5:
        r = math.ceil(absx)
    else:
        r = math.floor(absx)
    return copysign(r, x)

def isfinite(x):
    "NOT_RPYTHON"
    return not isinf(x) and not isnan(x)

def float_as_rbigint_ratio(value):
    from rpython.rlib.rbigint import rbigint

    if isinf(value):
        raise OverflowError("cannot pass infinity to as_integer_ratio()")
    elif isnan(value):
        raise ValueError("cannot pass nan to as_integer_ratio()")
    float_part, exp_int = math.frexp(value)
    for i in range(300):
        if float_part == math.floor(float_part):
            break
        float_part *= 2.0
        exp_int -= 1
    num = rbigint.fromfloat(float_part)
    den = rbigint.fromint(1)
    exp = den.lshift(abs(exp_int))
    if exp_int > 0:
        num = num.mul(exp)
    else:
        den = exp
    return num, den



# Implementation of the error function, the complimentary error function, the
# gamma function, and the natural log of the gamma function.  These exist in
# libm, but I hear those implementations are horrible.

ERF_SERIES_CUTOFF = 1.5
ERF_SERIES_TERMS = 25
ERFC_CONTFRAC_CUTOFF = 30.
ERFC_CONTFRAC_TERMS = 50
_sqrtpi = 1.772453850905516027298167483341145182798

def _erf_series(x):
    x2 = x * x
    acc = 0.
    fk = ERF_SERIES_TERMS + .5
    for i in range(ERF_SERIES_TERMS):
        acc = 2.0 + x2 * acc / fk
        fk -= 1.
    return acc * x * math.exp(-x2) / _sqrtpi

def _erfc_contfrac(x):
    if x >= ERFC_CONTFRAC_CUTOFF:
        return 0.
    x2 = x * x
    a = 0.
    da = .5
    p = 1.
    p_last = 0.
    q = da + x2
    q_last = 1.
    for i in range(ERFC_CONTFRAC_TERMS):
        a += da
        da += 2.
        b = da + x2
        p_last, p = p, b * p - a * p_last
        q_last, q = q, b * q - a * q_last
    return p / q * x * math.exp(-x2) / _sqrtpi

def erf(x):
    """The error function at x."""
    if isnan(x):
        return x
    absx = abs(x)
    if absx < ERF_SERIES_CUTOFF:
        return _erf_series(x)
    else:
        cf = _erfc_contfrac(absx)
        return 1. - cf if x > 0. else cf - 1.

def erfc(x):
    """The complementary error function at x."""
    if isnan(x):
        return x
    absx = abs(x)
    if absx < ERF_SERIES_CUTOFF:
        return 1. - _erf_series(x)
    else:
        cf = _erfc_contfrac(absx)
        return cf if x > 0. else 2. - cf

def _sinpi(x):
    y = math.fmod(abs(x), 2.)
    n = int(round_away(2. * y))
    if n == 0:
        r = math.sin(math.pi * y)
    elif n == 1:
        r = math.cos(math.pi * (y - .5))
    elif n == 2:
        r = math.sin(math.pi * (1. - y))
    elif n == 3:
        r = -math.cos(math.pi * (y - 1.5))
    elif n == 4:
        r = math.sin(math.pi * (y - 2.))
    else:
        raise AssertionError("should not reach")
    return copysign(1., x) * r

_lanczos_g = 6.024680040776729583740234375
_lanczos_g_minus_half = 5.524680040776729583740234375
_lanczos_num_coeffs = [
    23531376880.410759688572007674451636754734846804940,
    42919803642.649098768957899047001988850926355848959,
    35711959237.355668049440185451547166705960488635843,
    17921034426.037209699919755754458931112671403265390,
    6039542586.3520280050642916443072979210699388420708,
    1439720407.3117216736632230727949123939715485786772,
    248874557.86205415651146038641322942321632125127801,
    31426415.585400194380614231628318205362874684987640,
    2876370.6289353724412254090516208496135991145378768,
    186056.26539522349504029498971604569928220784236328,
    8071.6720023658162106380029022722506138218516325024,
    210.82427775157934587250973392071336271166969580291,
    2.5066282746310002701649081771338373386264310793408
]
_lanczos_den_coeffs = [
    0.0, 39916800.0, 120543840.0, 150917976.0, 105258076.0, 45995730.0,
    13339535.0, 2637558.0, 357423.0, 32670.0, 1925.0, 66.0, 1.0]
LANCZOS_N = len(_lanczos_den_coeffs)
_lanczos_n_iter = unroll.unrolling_iterable(range(LANCZOS_N))
_lanczos_n_iter_back = unroll.unrolling_iterable(range(LANCZOS_N - 1, -1, -1))
_gamma_integrals = [
    1.0, 1.0, 2.0, 6.0, 24.0, 120.0, 720.0, 5040.0, 40320.0, 362880.0,
    3628800.0, 39916800.0, 479001600.0, 6227020800.0, 87178291200.0,
    1307674368000.0, 20922789888000.0, 355687428096000.0,
    6402373705728000.0, 121645100408832000.0, 2432902008176640000.0,
    51090942171709440000.0, 1124000727777607680000.0]

def _lanczos_sum(x):
    num = 0.
    den = 0.
    assert x > 0.
    if x < 5.:
        for i in _lanczos_n_iter_back:
            num = num * x + _lanczos_num_coeffs[i]
            den = den * x + _lanczos_den_coeffs[i]
    else:
        for i in _lanczos_n_iter:
            num = num / x + _lanczos_num_coeffs[i]
            den = den / x + _lanczos_den_coeffs[i]
    return num / den

def gamma(x):
    """Compute the gamma function for x."""
    if isnan(x) or (isinf(x) and x > 0.):
        return x
    if isinf(x):
        raise ValueError("math domain error")
    if x == 0.:
        raise ValueError("math domain error")
    if x == math.floor(x):
        if x < 0.:
            raise ValueError("math domain error")
        if x < len(_gamma_integrals):
            return _gamma_integrals[int(x) - 1]
    absx = abs(x)
    if absx < 1e-20:
        r = 1. / x
        if isinf(r):
            raise OverflowError("math range error")
        return r
    if absx > 200.:
        if x < 0.:
            return 0. / -_sinpi(x)
        else:
            raise OverflowError("math range error")
    y = absx + _lanczos_g_minus_half
    if absx > _lanczos_g_minus_half:
        q = y - absx
        z = q - _lanczos_g_minus_half
    else:
        q = y - _lanczos_g_minus_half
        z = q - absx
    z = z * _lanczos_g / y
    if x < 0.:
        r = -math.pi / _sinpi(absx) / absx * math.exp(y) / _lanczos_sum(absx)
        r -= z * r
        if absx < 140.:
            r /= math.pow(y, absx - .5)
        else:
            sqrtpow = math.pow(y, absx / 2. - .25)
            r /= sqrtpow
            r /= sqrtpow
    else:
        r = _lanczos_sum(absx) / math.exp(y)
        r += z * r
        if absx < 140.:
            r *= math.pow(y, absx - .5)
        else:
            sqrtpow = math.pow(y, absx / 2. - .25)
            r *= sqrtpow
            r *= sqrtpow
    if isinf(r):
        raise OverflowError("math range error")
    return r

def lgamma(x):
    """Compute the natural logarithm of the gamma function for x."""
    if isnan(x):
        return x
    if isinf(x):
        return INFINITY
    if x == math.floor(x) and x <= 2.:
        if x <= 0.:
            raise ValueError("math range error")
        return 0.
    absx = abs(x)
    if absx < 1e-20:
        return -math.log(absx)
    if x > 0.:
        r = (math.log(_lanczos_sum(x)) - _lanczos_g + (x - .5) *
             (math.log(x + _lanczos_g - .5) - 1))
    else:
        r = (math.log(math.pi) - math.log(abs(_sinpi(absx))) - math.log(absx) -
             (math.log(_lanczos_sum(absx)) - _lanczos_g +
              (absx - .5) * (math.log(absx + _lanczos_g - .5) - 1)))
    if isinf(r):
        raise OverflowError("math domain error")
    return r


def to_ulps(x):
    """Convert a non-NaN float x to an integer, in such a way that
    adjacent floats are converted to adjacent integers.  Then
    abs(ulps(x) - ulps(y)) gives the difference in ulps between two
    floats.

    The results from this function will only make sense on platforms
    where C doubles are represented in IEEE 754 binary64 format.

    """
    n = struct.unpack('<q', struct.pack('<d', x))[0]
    if n < 0:
        n = ~(n+2**63)
    return n

def ulps_check(expected, got, ulps=20):
    """Given non-NaN floats `expected` and `got`,
    check that they're equal to within the given number of ulps.

    Returns None on success and an error message on failure."""

    ulps_error = to_ulps(got) - to_ulps(expected)
    if abs(ulps_error) <= ulps:
        return None
    return "error = {} ulps; permitted error = {} ulps".format(ulps_error,
                                                               ulps)

def acc_check(expected, got, rel_err=2e-15, abs_err = 5e-323):
    """Determine whether non-NaN floats a and b are equal to within a
    (small) rounding error.  The default values for rel_err and
    abs_err are chosen to be suitable for platforms where a float is
    represented by an IEEE 754 double.  They allow an error of between
    9 and 19 ulps."""

    # need to special case infinities, since inf - inf gives nan
    if math.isinf(expected) and got == expected:
        return None

    error = got - expected

    permitted_error = max(abs_err, rel_err * abs(expected))
    if abs(error) < permitted_error:
        return None
    return "error = {}; permitted error = {}".format(error,
                                                     permitted_error)
