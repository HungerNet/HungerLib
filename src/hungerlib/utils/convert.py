from types import SimpleNamespace
from mapres import datamap, res


@datamap.pipes
class TimeUnits:
    ns: float = 1e-9
    us: float = 1e-6
    ms: float = 1e-3
    s:  float = 1
    min: float = 60
    h: float = 3600
    day: float = 86400
time_units = TimeUnits()


@datamap.pipes
class ByteUnits:
    # decimal
    b: int = 1
    kb: int = 1_000
    mb: int = 1_000_000
    gb: int = 1_000_000_000
    tb: int = 1_000_000_000_000

    # binary
    kib: int = 1024
    mib: int = 1024**2
    gib: int = 1024**3
    tib: int = 1024**4
byte_units = ByteUnits()


def _time(value, src, dst, rounding=None):
    value = float(value)

    src_factor = float(getattr(time_units, src))
    dst_factor = float(getattr(time_units, dst))

    base = value * src_factor
    result = base / dst_factor

    return round(result, rounding) if rounding is not None else result


def _byte(value, src, dst, rounding=None):
    value = float(value)

    src_factor = float(getattr(byte_units, src))
    dst_factor = float(getattr(byte_units, dst))

    base = value * src_factor
    result = base / dst_factor

    return round(result, rounding) if rounding is not None else result


convert = SimpleNamespace(
    time=_time,
    byte=_byte,
)
