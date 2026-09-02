"""Test statistics engine."""

import pytest
from datetime import datetime, timedelta
from ledger.models import Trade
from ledger.stats import StatsEngine
import numpy as np


def create_trade(position_id, profit, direction="BUY", source="EA LIVE", entry_offset_days=0):
    """Helper to create a test trade."""
    entry_time = datetime(2026, 1, 1, 10, 0) + timedelta(days=entry_offset_days)
    trade = Trade(
        position_id=position_id,
        symbol="XAUUSD",
        entry_time=entry_time,
        entry_price=2050.00,
        exit_time=entry_time + timedelta(hours=2),
        exit_price=2050.00 + (profit if direction == "BUY" else -profit),
        volume=1.0,
        commission=1.0,
        swap=0.5,
        profit=profit,
        direction=direction,
        source=source,
        stop_loss=2040.00 if direction == "BUY" else 2060.00,
    )
    trade.calculate_r()
    return trade


def test_bootstrap_ci():
    """Test bootstrap confidence interval calculation."""
    engine = StatsEngine()
    values = [0.5, 0.6, 0.7, 0.8, 0.9]
    mean, ci_lower, ci_upper = engine._bootstrap_ci(values)
    
    assert mean == pytest.approx(0.7, abs=0.01)
    assert ci_lower < ci_upper
    assert ci_lower < mean < ci_upper


def test_backtest_filtering():
    """Test that backtests are excluded from analysis."""
    engine = StatsEngine()
    
    live_trades = [create_trade(i, 5.0, source="EA LIVE") for i in range(1, 31)]
    backtest_trades = [create_trade(100 + i, 5.0, source="EA BACKTEST") for i in range(1, 11)]
    
    all_trades = live_trades + backtest_trades
    report = engine.analyse(all_trades)
    
    # Only live trades should be counted
    assert report.total_trades == 30


def test_win_rate_calculation():
    """Test win rate calculation."""
    engine = StatsEngine()
    
    trades = []
    for i in range(1, 21):  # 20 trades
        profit = 5.0 if i <= 15 else -5.0  # 15 wins, 5 losses
        trades.append(create_trade(i, profit))
    
    report = engine.analyse(trades)
    
    assert report.total_trades == 20
    assert report.win_count == 15
    assert report.loss_count == 5
    assert report.win_rate == pytest.approx(0.75)


def test_underpowered_groups():
    """Test that groups with < 30 trades are marked as underpowered."""
    engine = StatsEngine()
    
    # Only 5 trades - underpowered
    trades = [create_trade(i, 5.0) for i in range(1, 6)]
    report = engine.analyse(trades)
    
    # Should not have any significant cuts
    holding_cuts = [c for c in report.cuts if c.bh_verdict == "holding"]
    assert len(holding_cuts) == 0


def test_bh_correction_applied():
    """Test that Benjamini-Hochberg correction is applied."""
    engine = StatsEngine()
    
    # Generate 40 trades with clear killzone effect
    trades = []
    for i in range(1, 21):
        # London zone (effective)
        trade = create_trade(i, 5.0)
        trade.ny_killzone = "London"
        trades.append(trade)
    
    for i in range(21, 41):
        # Outside (ineffective)
        trade = create_trade(i, -2.0)
        trade.ny_killzone = "Outside"
        trades.append(trade)
    
    report = engine.analyse(trades)
    
    # Check that verdicts are assigned
    verdicts = {c.bh_verdict for c in report.cuts if c.cut_name == "Killzone"}
    assert len(verdicts) > 0
    assert "NOT DEFINED" not in verdicts


def test_mean_r_calculation():
    """Test mean R and confidence intervals."""
    engine = StatsEngine()
    
    trades = [create_trade(i, float(i)) for i in range(1, 31)]  # R values from 0.1 to 3.0
    report = engine.analyse(trades)
    
    assert report.mean_r > 0
    assert report.mean_r_ci_lower < report.mean_r
    assert report.mean_r < report.mean_r_ci_upper
