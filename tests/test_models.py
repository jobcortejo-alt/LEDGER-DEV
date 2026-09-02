"""Test Trade model and R arithmetic."""

import pytest
from datetime import datetime
from ledger.models import Trade, aggregate_deals


def test_buy_r_calculation():
    """Test R calculation for BUY trade."""
    trade = Trade(
        position_id=1,
        symbol="XAUUSD",
        entry_time=datetime(2026, 1, 1, 10, 0),
        entry_price=2050.00,
        exit_time=datetime(2026, 1, 1, 12, 0),
        exit_price=2055.00,
        volume=1.0,
        commission=1.0,
        swap=0.5,
        profit=4.5,
        direction="BUY",
        stop_loss=2040.00,
    )
    
    r = trade.calculate_r()
    assert r == pytest.approx(0.45, abs=0.01)  # 4.5 / 10 = 0.45


def test_sell_r_calculation():
    """Test R calculation for SELL trade."""
    trade = Trade(
        position_id=1,
        symbol="XAUUSD",
        entry_time=datetime(2026, 1, 1, 10, 0),
        entry_price=2050.00,
        exit_time=datetime(2026, 1, 1, 12, 0),
        exit_price=2045.00,
        volume=1.0,
        commission=1.0,
        swap=0.5,
        profit=4.5,
        direction="SELL",
        stop_loss=2060.00,
    )
    
    r = trade.calculate_r()
    assert r == pytest.approx(0.45, abs=0.01)  # 4.5 / 10 = 0.45


def test_r_no_stop_loss():
    """Test R returns None when stop loss not set."""
    trade = Trade(
        position_id=1,
        symbol="XAUUSD",
        entry_time=datetime(2026, 1, 1, 10, 0),
        entry_price=2050.00,
        exit_time=datetime(2026, 1, 1, 12, 0),
        exit_price=2055.00,
        volume=1.0,
        commission=1.0,
        swap=0.5,
        profit=4.5,
        direction="BUY",
        stop_loss=None,
    )
    
    r = trade.calculate_r()
    assert r is None


def test_trade_validation():
    """Test trade validation."""
    # Invalid: negative volume
    trade = Trade(
        position_id=1,
        symbol="XAUUSD",
        entry_time=datetime(2026, 1, 1, 10, 0),
        entry_price=2050.00,
        exit_time=datetime(2026, 1, 1, 12, 0),
        exit_price=2055.00,
        volume=-1.0,
        commission=1.0,
        swap=0.5,
        profit=4.5,
        direction="BUY",
    )
    
    errors = trade.validate()
    assert len(errors) > 0
    assert "Volume must be positive" in errors


def test_trade_is_win():
    """Test win/loss detection."""
    trade_win = Trade(
        position_id=1,
        symbol="XAUUSD",
        entry_time=datetime(2026, 1, 1, 10, 0),
        entry_price=2050.00,
        exit_time=datetime(2026, 1, 1, 12, 0),
        exit_price=2055.00,
        volume=1.0,
        commission=1.0,
        swap=0.5,
        profit=5.0,
        direction="BUY",
    )
    assert trade_win.is_win()
    assert not trade_win.is_loss()
    
    trade_loss = Trade(
        position_id=2,
        symbol="XAUUSD",
        entry_time=datetime(2026, 1, 1, 10, 0),
        entry_price=2050.00,
        exit_time=datetime(2026, 1, 1, 12, 0),
        exit_price=2045.00,
        volume=1.0,
        commission=1.0,
        swap=0.5,
        profit=-5.0,
        direction="BUY",
    )
    assert trade_loss.is_loss()
    assert not trade_loss.is_win()


def test_partial_close_aggregation():
    """Test aggregation of partial closes."""
    deals = [
        {"position_id": 100, "symbol": "XAUUSD", "direction": "BUY", "entry_time": datetime(2026, 1, 1, 10, 0), "entry_price": 2050.00, "exit_time": datetime(2026, 1, 1, 10, 0), "exit_price": 2050.00, "volume": 1.0, "commission": 0.5, "swap": 0, "profit": 0, "source": "EA LIVE"},
        {"position_id": 100, "symbol": "XAUUSD", "direction": "SELL", "entry_time": datetime(2026, 1, 1, 12, 0), "entry_price": 2060.00, "exit_time": datetime(2026, 1, 1, 12, 0), "exit_price": 2060.00, "volume": 0.5, "commission": 0.25, "swap": 0, "profit": 5.0, "source": "EA LIVE"},
        {"position_id": 100, "symbol": "XAUUSD", "direction": "SELL", "entry_time": datetime(2026, 1, 1, 13, 0), "entry_price": 2061.00, "exit_time": datetime(2026, 1, 1, 13, 0), "exit_price": 2061.00, "volume": 0.5, "commission": 0.25, "swap": 0, "profit": 5.0, "source": "EA LIVE"},
    ]
    
    trade = aggregate_deals(deals)
    
    assert trade.position_id == 100
    assert trade.volume == pytest.approx(1.0)
    assert trade.commission == pytest.approx(1.0)
    assert trade.profit == pytest.approx(10.0)
    # Weighted exit price: (2060*0.5 + 2061*0.5) / 1.0 = 2060.5
    assert trade.exit_price == pytest.approx(2060.5)


def test_backtest_isolation():
    """Test backtest trades are marked correctly."""
    backtest_trade = Trade(
        position_id=1,
        symbol="XAUUSD",
        entry_time=datetime(2026, 1, 1, 10, 0),
        entry_price=2050.00,
        exit_time=datetime(2026, 1, 1, 12, 0),
        exit_price=2055.00,
        volume=1.0,
        commission=1.0,
        swap=0.5,
        profit=4.5,
        direction="BUY",
        source="EA BACKTEST",
    )
    
    assert backtest_trade.is_backtest()


def test_premises_count():
    """Test premise counting."""
    trade = Trade(
        position_id=1,
        symbol="XAUUSD",
        entry_time=datetime(2026, 1, 1, 10, 0),
        entry_price=2050.00,
        exit_time=datetime(2026, 1, 1, 12, 0),
        exit_price=2055.00,
        volume=1.0,
        commission=1.0,
        swap=0.5,
        profit=4.5,
        direction="BUY",
        premises_met=[0, 1, 2, 3, 4, 5, 6],
    )
    
    assert trade.premise_count() == 7
    assert trade.has_complete_premises()
