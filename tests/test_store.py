"""Test database store."""

import pytest
from datetime import datetime
from ledger.store import Store
from ledger.models import Trade


def test_insert_and_get_trade(store, sample_trade):
    """Test inserting and retrieving a trade."""
    trade_id = store.insert_trade(sample_trade)
    assert trade_id is not None
    
    retrieved = store.get_trade(sample_trade.position_id)
    assert retrieved is not None
    assert retrieved.position_id == sample_trade.position_id
    assert retrieved.symbol == sample_trade.symbol


def test_duplicate_position_id(store, sample_trade):
    """Test that duplicate position IDs are rejected."""
    store.insert_trade(sample_trade)
    
    with pytest.raises(ValueError):
        store.insert_trade(sample_trade)


def test_update_trade(store, sample_trade):
    """Test updating a trade."""
    store.insert_trade(sample_trade)
    
    retrieved = store.get_trade(sample_trade.position_id)
    retrieved.bias = "Bullish"
    retrieved.notes = "Good setup"
    store.update_trade(retrieved)
    
    updated = store.get_trade(sample_trade.position_id)
    assert updated.bias == "Bullish"
    assert updated.notes == "Good setup"


def test_delete_trade(store, sample_trade):
    """Test deleting a trade."""
    store.insert_trade(sample_trade)
    assert store.get_trade(sample_trade.position_id) is not None
    
    store.delete_trade(sample_trade.position_id)
    assert store.get_trade(sample_trade.position_id) is None


def test_list_trades(store):
    """Test listing trades."""
    for i in range(5):
        trade = Trade(
            position_id=i,
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
            source="EA LIVE",
        )
        store.insert_trade(trade)
    
    trades = store.list_trades(exclude_backtest=True)
    assert len(trades) == 5


def test_backtest_filtering(store):
    """Test filtering out backtests."""
    live_trade = Trade(
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
        source="EA LIVE",
    )
    
    backtest_trade = Trade(
        position_id=2,
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
    
    store.insert_trade(live_trade)
    store.insert_trade(backtest_trade)
    
    live_only = store.list_trades(exclude_backtest=True)
    assert len(live_only) == 1
    assert live_only[0].position_id == 1
    
    all_trades = store.list_trades(exclude_backtest=False)
    assert len(all_trades) == 2


def test_count_trades(store):
    """Test trade counting."""
    for i in range(3):
        trade = Trade(
            position_id=i,
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
            source="EA LIVE",
        )
        store.insert_trade(trade)
    
    assert store.count_trades(exclude_backtest=True) == 3
