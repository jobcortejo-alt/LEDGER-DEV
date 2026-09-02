"""Test utilities and timezone handling."""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from ledger.utils import (
    classify_killzone,
    classify_macro,
    normalise_symbol,
    is_leap_year,
    days_in_month,
    bootstrap_ci,
)


def test_killzone_london():
    """Test London killzone classification."""
    # 2:00 AM NY time
    dt = datetime(2026, 1, 1, 7, 0, 0, tzinfo=ZoneInfo("UTC"))  # 2 AM NY
    kz = classify_killzone(dt)
    assert kz == "London"


def test_killzone_new_york():
    """Test New York killzone classification."""
    # 7:00 AM NY time
    dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("UTC"))  # 7 AM NY
    kz = classify_killzone(dt)
    assert kz == "New York"


def test_killzone_asian():
    """Test Asian killzone classification."""
    # 7:00 PM NY time
    dt = datetime(2026, 1, 2, 0, 0, 0, tzinfo=ZoneInfo("UTC"))  # 7 PM NY
    kz = classify_killzone(dt)
    assert kz == "Asian"


def test_macro_european():
    """Test European macro session."""
    dt = datetime(2026, 1, 1, 7, 0, 0, tzinfo=ZoneInfo("UTC"))  # 2 AM NY
    macro = classify_macro(dt)
    assert macro == "European"


def test_macro_american():
    """Test American macro session."""
    dt = datetime(2026, 1, 1, 14, 0, 0, tzinfo=ZoneInfo("UTC"))  # 9 AM NY
    macro = classify_macro(dt)
    assert macro == "American"


def test_macro_asian():
    """Test Asian macro session."""
    dt = datetime(2026, 1, 2, 2, 0, 0, tzinfo=ZoneInfo("UTC"))  # 9 PM NY
    macro = classify_macro(dt)
    assert macro == "Asian"


def test_symbol_normalisation():
    """Test symbol normalisation."""
    assert normalise_symbol("XAUUSD") == "XAUUSD"
    assert normalise_symbol("xauusd") == "XAUUSD"
    assert normalise_symbol("GOLD") == "XAUUSD"
    assert normalise_symbol("XAUUSD.a") == "XAUUSD"


def test_leap_year():
    """Test leap year detection."""
    assert is_leap_year(2024) == True
    assert is_leap_year(2026) == False
    assert is_leap_year(2000) == True
    assert is_leap_year(1900) == False


def test_days_in_month():
    """Test days in month calculation."""
    assert days_in_month(2026, 1) == 31  # January
    assert days_in_month(2026, 2) == 28  # February (non-leap)
    assert days_in_month(2024, 2) == 29  # February (leap)
    assert days_in_month(2026, 4) == 30  # April


def test_bootstrap_ci():
    """Test bootstrap confidence interval."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    lower, mean, upper = bootstrap_ci(values, nsamples=1000, seed=42)
    
    assert lower < mean
    assert mean < upper
    assert mean == pytest.approx(3.0, abs=0.5)
