"""One clock for every 'what day is it' question. The server runs UTC; the app lives in America/New_York.
Returns naive ET datetimes so they compare with stored (naive local) DB timestamps. Tests patch apptime.now_local."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

APP_TZ = ZoneInfo('America/New_York')


def now_local():
    """Naive wall-clock datetime in America/New_York."""
    return datetime.now(APP_TZ).replace(tzinfo=None)


def today_local():
    return now_local().date()


def day_start(d=None):
    """Naive midnight at the start of day d (default: today in ET)."""
    d = d or today_local()
    return datetime(d.year, d.month, d.day)


def day_window(d=None):
    s = day_start(d)
    return s, s + timedelta(days=1)


UTC = timezone.utc


def now_utc_naive():
    """Naive UTC 'now' for stored timestamps. Derived from now_local so one patch freezes both."""
    return now_local().replace(tzinfo=APP_TZ).astimezone(UTC).replace(tzinfo=None)


def to_local(dt):
    """Stored naive-UTC timestamp -> naive ET wall time (for bucketing into ET days)."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC).astimezone(APP_TZ).replace(tzinfo=None)


def local_date(dt):
    loc = to_local(dt)
    return loc.date() if loc else None


def day_bounds_utc(d=None):
    """(start, end) of ET day d as naive UTC datetimes (DST-correct)."""
    d = d or today_local()
    s = datetime(d.year, d.month, d.day, tzinfo=APP_TZ)
    e = datetime.combine(d + timedelta(days=1), datetime.min.time(), tzinfo=APP_TZ)
    return s.astimezone(UTC).replace(tzinfo=None), e.astimezone(UTC).replace(tzinfo=None)


def week_bounds_utc(days=7, d=None):
    """UTC bounds covering the `days` ET days ending with d (inclusive)."""
    d = d or today_local()
    return day_bounds_utc(d - timedelta(days=days - 1))[0], day_bounds_utc(d)[1]
