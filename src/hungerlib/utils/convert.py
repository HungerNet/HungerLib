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


def _time(value, src, dst, rounding=None):
    src_factor = res(f"|{src}|", TimeUnits)
    dst_factor = res(f"|{dst}|", TimeUnits)

    base = float(value) * src_factor
    result = base / dst_factor

    return round(result, rounding) if rounding is not None else result


def _byte(value, src, dst, rounding=None):
    src_factor = res(f"|{src}|", ByteUnits)
    dst_factor = res(f"|{dst}|", ByteUnits)

    base = float(value) * src_factor
    result = base / dst_factor

    return round(result, rounding) if rounding is not None else result


convert = SimpleNamespace(
    time=_time,
    byte=_byte,
)
