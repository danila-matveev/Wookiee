import pytz
from datetime import datetime, date
from agents.oleg import config

def get_msk_tz():
    """Return Moscow timezone object."""
    return pytz.timezone(config.TIMEZONE)

def get_now_msk() -> datetime:
    """Return current datetime in Moscow."""
    return datetime.now(get_msk_tz())

get_current_time_msk = get_now_msk

def get_today_msk() -> date:
    """Return current date in Moscow."""
    return get_now_msk().date()

def to_msk(dt: datetime) -> datetime:
    """Convert any datetime to Moscow timezone."""
    if dt.tzinfo is None:
        return get_msk_tz().localize(dt)
    return dt.astimezone(get_msk_tz())
