"""Utility functions for timezone, symbol normalisation, and helpers."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Tuple
import math


def get_ny_time(dt: datetime, from_tz: str = "UTC") -> datetime:
    """
    Convert datetime to New York time (ICT standard for killzones).
    
    Args:
        dt: datetime object (can be naive or aware)
        from_tz: timezone name if dt is naive
    
    Returns:
        datetime in America/New_York timezone
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(from_tz))
    
    ny_tz = ZoneInfo("America/New_York")
    return dt.astimezone(ny_tz)


def get_broker_time(dt: datetime, broker_tz: str) -> datetime:
    """
    Convert datetime to broker server time.
    
    Args:
        dt: datetime object (can be naive or aware)
        broker_tz: broker timezone name
    
    Returns:
        datetime in broker timezone
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    
    tz = ZoneInfo(broker_tz)
    return dt.astimezone(tz)


def get_local_time(dt: datetime) -> datetime:
    """
    Convert datetime to user's local system timezone.
    
    Args:
        dt: datetime object (can be naive or aware)
    
    Returns:
        datetime in local timezone
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    
    return dt.astimezone()


def classify_killzone(dt: datetime, reference_tz: str = "America/New_York") -> str:
    """
    Classify a datetime into an ICT killzone.
    
    Args:
        dt: datetime to classify (in any timezone)
        reference_tz: timezone to use for classification
    
    Returns:
        "London", "New York", "Asian", or "Outside"
    """
    ny_dt = get_ny_time(dt, from_tz="UTC")
    hour = ny_dt.hour
    
    if 2 <= hour < 5:
        return "London"
    elif 7 <= hour < 10:
        return "New York"
    elif 19 <= hour < 22:
        return "Asian"
    else:
        return "Outside"


def classify_macro(dt: datetime, reference_tz: str = "America/New_York") -> str:
    """
    Classify a datetime into a macro session.
    
    Args:
        dt: datetime to classify (in any timezone)
        reference_tz: timezone to use for classification
    
    Returns:
        "European", "American", or "Asian"
    """
    ny_dt = get_ny_time(dt, from_tz="UTC")
    hour = ny_dt.hour
    
    if 2 <= hour < 12:
        return "European"
    elif 12 <= hour < 20:
        return "American"
    else:
        return "Asian"


def normalise_symbol(symbol: str, broker_suffix: str = "") -> str:
    """
    Normalise symbol to canonical form.
    
    Args:
        symbol: raw symbol from broker
        broker_suffix: broker's typical suffix to strip (e.g., ".a")
    
    Returns:
        canonical symbol
    """
    symbol = symbol.upper().strip()
    
    # Strip common broker suffixes
    for suffix in [".a", ".b", ".pro", ".live", "#"]:
        if symbol.endswith(suffix):
            symbol = symbol[:-len(suffix)]
    
    # Map common variants to canonical
    mapping = {
        "GOLD": "XAUUSD",
        "XAUU": "XAUUSD",
    }
    
    return mapping.get(symbol, symbol)


def calculate_pnl_percent(entry: float, exit: float, direction: str) -> float:
    """
    Calculate P&L percentage.
    
    Args:
        entry: entry price
        exit: exit price
        direction: "BUY" or "SELL"
    
    Returns:
        profit/loss percentage
    """
    if entry <= 0:
        return 0.0
    
    if direction.upper() == "BUY":
        return ((exit - entry) / entry) * 100
    elif direction.upper() == "SELL":
        return ((entry - exit) / entry) * 100
    else:
        return 0.0


def get_month_bounds(year: int, month: int, tz: str = None) -> Tuple[datetime, datetime]:
    """
    Get start and end datetime for a calendar month in given timezone.
    
    Args:
        year: year
        month: month (1-12)
        tz: timezone name (defaults to local)
    
    Returns:
        (month_start, month_end) both as datetime objects
    """
    if tz is None:
        tz = str(datetime.now().astimezone().tzinfo)
    
    zone = ZoneInfo(tz)
    
    # Start of month
    start = datetime(year, month, 1, 0, 0, 0, tzinfo=zone)
    
    # End of month (first day of next month minus 1 second)
    if month == 12:
        end = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=zone) - timedelta(seconds=1)
    else:
        end = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=zone) - timedelta(seconds=1)
    
    return start, end


def is_leap_year(year: int) -> bool:
    """Return True if year is a leap year."""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def days_in_month(year: int, month: int) -> int:
    """Return number of days in month."""
    days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if month == 2 and is_leap_year(year):
        return 29
    return days[month - 1]


def bootstrap_ci(values: list, nsamples: int = 10000, seed: int = 42) -> Tuple[float, float, float]:
    """
    Calculate bootstrap confidence interval for a list of values.
    
    Args:
        values: list of numeric values
        nsamples: number of bootstrap resamples
        seed: random seed for reproducibility
    
    Returns:
        (lower_ci, mean, upper_ci) as 95% percentile interval
    """
    if not values:
        return 0.0, 0.0, 0.0
    
    import numpy as np
    
    np.random.seed(seed)
    
    values = np.array(values)
    means = []
    
    for _ in range(nsamples):
        resample = np.random.choice(values, size=len(values), replace=True)
        means.append(np.mean(resample))
    
    means = np.array(means)
    mean = np.mean(values)
    lower = np.percentile(means, 2.5)
    upper = np.percentile(means, 97.5)
    
    return float(lower), float(mean), float(upper)
