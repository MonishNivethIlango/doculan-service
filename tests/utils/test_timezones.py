import datetime
import pytest
from utils.timezones import TimeZoneUtils, DATETIME_FORMAT

@pytest.fixture
def tz():
    return TimeZoneUtils('UTC')

def test_get_timezone_datetime(tz):
    dt = tz.get_timezone_datetime()
    assert isinstance(dt, datetime.datetime)
    assert dt.tzinfo is not None

def test_get_timezone_timestamp(tz):
    ts = tz.get_timezone_timestamp()
    assert isinstance(ts, int)
    assert abs(ts - int(datetime.datetime.now(datetime.timezone.utc).timestamp())) < 10

def test_get_timezone_milliseconds(tz):
    ms = tz.get_timezone_milliseconds()
    assert isinstance(ms, int)
    assert abs(ms - int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)) < 10000

def test_datetime_to_timezone_str(tz):
    now = datetime.datetime.now(datetime.timezone.utc)
    s = tz.datetime_to_timezone_str(now)
    assert isinstance(s, str)
    assert len(s) > 0

def test_datetime_to_timezone_datetime(tz):
    now = datetime.datetime.now(datetime.timezone.utc)
    dt = tz.datetime_to_timezone_datetime(now)
    assert isinstance(dt, datetime.datetime)
    assert dt.tzinfo is not None

def test_datetime_to_timezone_utc():
    now = datetime.datetime.now(datetime.timezone.utc)
    dt = TimeZoneUtils.datetime_to_timezone_utc(now)
    assert isinstance(dt, datetime.datetime)
    assert dt.tzinfo is not None
    assert dt.tzinfo.key == 'UTC'

def test_datetime_to_timezone_timestamp(tz):
    now = datetime.datetime.now(datetime.timezone.utc)
    ts = tz.datetime_to_timezone_timestamp(now)
    assert isinstance(ts, int)

def test_datetime_to_timezone_milliseconds(tz):
    now = datetime.datetime.now(datetime.timezone.utc)
    ms = tz.datetime_to_timezone_milliseconds(now)
    assert isinstance(ms, int)

def test_str_to_timezone_utc(tz):
    now = datetime.datetime.now(datetime.timezone.utc)
    s = now.strftime(DATETIME_FORMAT)
    dt = tz.str_to_timezone_utc(s)
    assert isinstance(dt, datetime.datetime)
    assert dt.tzinfo.key == 'UTC'

def test_str_to_timezone_datetime(tz):
    now = datetime.datetime.now(datetime.timezone.utc)
    s = now.strftime(DATETIME_FORMAT)
    dt = tz.str_to_timezone_datetime(s)
    assert isinstance(dt, datetime.datetime)
    assert dt.tzinfo is not None

def test_utc_datetime_to_timezone_datetime(tz):
    now = datetime.datetime.now(datetime.timezone.utc)
    dt = tz.utc_datetime_to_timezone_datetime(now)
    assert isinstance(dt, datetime.datetime)
    assert dt.tzinfo is not None

def test_utc_timestamp_to_timezone_datetime(tz):
    now = datetime.datetime.now(datetime.timezone.utc)
    ts = int(now.timestamp())
    dt = tz.utc_timestamp_to_timezone_datetime(ts)
    assert isinstance(dt, datetime.datetime)
    assert dt.tzinfo is not None

def test_get_timezone_expire_time(tz):
    delta = datetime.timedelta(seconds=60)
    expire = tz.get_timezone_expire_time(delta)
    assert isinstance(expire, datetime.datetime)
    assert expire > tz.get_timezone_datetime()

def test_get_timezone_expire_seconds(tz):
    future = tz.get_timezone_datetime() + datetime.timedelta(seconds=60)
    seconds = tz.get_timezone_expire_seconds(future)
    assert isinstance(seconds, int)
    assert 0 <= seconds <= 60

def test_format_size(tz):
    assert tz.format_size(0) == "0 B"
    assert tz.format_size(1023) == "1023.0 B"
    assert tz.format_size(1024) == "1.0 KB"
    assert tz.format_size(1024*1024) == "1.0 MB"

def test_format_datetime(tz):
    now = datetime.datetime.now(datetime.timezone.utc)
    s = tz.format_datetime(now)
    assert isinstance(s, str)
    assert "UTC" in s
