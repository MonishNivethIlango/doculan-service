import datetime
from zoneinfo import ZoneInfo
from datetime import timezone
import math

DATETIME_TIMEZONE: str = 'US/Central'
DATETIME_FORMAT: str = '%Y-%m-%d %H:%M:%S'
class TimeZoneUtils:
    def __init__(self, timezone_str=DATETIME_TIMEZONE):
        self.timezone = ZoneInfo(timezone_str)

    def get_timezone_datetime(self) -> datetime.datetime:
        """Get time zone time"""
        return datetime.datetime.now(self.timezone)

    def get_timezone_timestamp(self) -> int:
        """Get time zone timestamp (seconds)"""
        return int(self.get_timezone_datetime().timestamp())

    def get_timezone_milliseconds(self) -> int:
        """Get time zone timestamp (millisecond)"""
        return int(self.get_timezone_datetime().timestamp() * 1000)

    def datetime_to_timezone_str(self, dt: datetime.datetime, format_str: str = DATETIME_FORMAT) -> str:
        """Convert datetime object to time zone time string"""
        return dt.astimezone(self.timezone).strftime(format_str)

    def datetime_to_timezone_datetime(self, dt: datetime.datetime) -> datetime.datetime:
        """Convert datetime object to datetime time zone object"""
        return dt.astimezone(self.timezone)

    @staticmethod
    def datetime_to_timezone_utc(dt: datetime.datetime) -> datetime.datetime:
        """Convert datetime object to UTC"""
        return dt.astimezone(ZoneInfo("UTC"))

    def datetime_to_timezone_timestamp(self, dt: datetime.datetime) -> int:
        """Convert datetime object to time zone timestamp (seconds)"""
        return int(dt.astimezone(self.timezone).timestamp())

    def datetime_to_timezone_milliseconds(self, dt: datetime.datetime) -> int:
        """Convert datetime object to time zone timestamp (milliseconds)"""
        return int(dt.astimezone(self.timezone).timestamp() * 1000)

    def str_to_timezone_utc(self, time_str: str, format_str: str = DATETIME_FORMAT) -> datetime.datetime:
        """Convert time string to UTC datetime"""
        dt = datetime.datetime.strptime(time_str, format_str).replace(tzinfo=self.timezone)
        return self.datetime_to_timezone_utc(dt)

    def str_to_timezone_datetime(self, time_str: str, format_str: str = DATETIME_FORMAT) -> datetime.datetime:
        """Convert time string to datetime time zone object"""
        return datetime.datetime.strptime(time_str, format_str).replace(tzinfo=self.timezone)

    def utc_datetime_to_timezone_datetime(self, utc_time: datetime.datetime) -> datetime.datetime:
        """Convert UTC datetime object to time zone object"""
        return utc_time.replace(tzinfo=ZoneInfo("UTC")).astimezone(self.timezone)

    def utc_timestamp_to_timezone_datetime(self, timestamp: int) -> datetime.datetime:
        """Convert timestamp to datetime object with timezone"""
        utc_datetime = datetime.datetime.utcfromtimestamp(timestamp).replace(tzinfo=ZoneInfo("UTC"))
        return self.datetime_to_timezone_datetime(utc_datetime)

    def get_timezone_expire_time(self, expires_delta: datetime.timedelta) -> datetime.datetime:
        """Get time zone expiration time"""
        return self.get_timezone_datetime() + expires_delta

    def get_timezone_expire_seconds(self, expire_datetime: datetime.datetime) -> int:
        """Get time interval (seconds) from specified time to current time"""
        timezone_datetime = self.get_timezone_datetime()
        expire_datetime = self.datetime_to_timezone_datetime(expire_datetime)
        if expire_datetime < timezone_datetime:
            return 0
        return int((expire_datetime - timezone_datetime).total_seconds())

    def format_size(self, size_bytes):
        if size_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

    def format_datetime(self, dt):
        return dt.astimezone(timezone.utc).strftime("%b %d, %Y %I:%M %p UTC")

timezone_utils = TimeZoneUtils()
