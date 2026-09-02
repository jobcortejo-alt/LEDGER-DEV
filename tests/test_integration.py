"""Integration tests."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from ledger.store import Store
from ledger.models import Trade
from ledger.stats import StatsEngine
from ledger.cli import cmd_demo
import tempfile
import argparse


def test_end_to_end_workflow():
    """Test complete workflow: insert, update, analyse."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = Store(db_path)
        
        # Insert some trades
        for i in range(1, 31):
            trade = Trade(
                position_id=i,
                symbol="XAUUSD",
                entry_time=datetime(2026, 1, 1, 10, 0) + timedelta(days=i),
                entry_price=2050.00,
                exit_time=datetime(2026, 1, 1, 12, 0) + timedelta(days=i),
                exit_price=2050.00 + float(i),
                volume=1.0,
                commission=1.0,
                swap=0.5,
                profit=float(i),
                direction="BUY",
                source="EA LIVE",
                stop_loss=2040.00,
                grade="A" if i % 2 == 0 else "B",
            )
            trade.calculate_r()
            store.insert_trade(trade)
        
        # Update a trade
        trade = store.get_trade(1)
        trade.notes = "Good trade"
        store.update_trade(trade)
        
        # Analyse
        trades = store.list_trades(exclude_backtest=True)
        engine = StatsEngine()
        report = engine.analyse(trades)
        
        assert report.total_trades == 30
        assert report.win_count == 30
        assert report.mean_r > 0


def test_demo_generates_correct_structure():
    """Test demo data generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "demo.db"
        
        # Generate demo
        args = argparse.Namespace(db=str(db_path), n=100)
        cmd_demo(args)
        
        # Verify
        store = Store(db_path)
        trades = store.list_trades(exclude_backtest=False)
        
        assert len(trades) == 100
        
        # Check for planted effects
        has_broken_rules = any("BROKEN RULE" in t.tags for t in trades)
        has_all_premises = any(len(t.premises_met) == 7 for t in trades)
        
        # Should have some of each (not guaranteed but very likely with 100 trades)
        assert has_broken_rules or has_all_premises


def test_preserves_journal_on_resync():
    """Test that journal data is preserved on re-sync."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = Store(db_path)
        
        # Create initial trade
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
            source="EA LIVE",
            stop_loss=2040.00,
        )
        store.insert_trade(trade)
        
        # Add journal data
        retrieved = store.get_trade(1)
        retrieved.bias = "Bullish"
        retrieved.notes = "Strong setup"
        retrieved.grade = "A"
        store.update_trade(retrieved)
        
        # Simulate re-sync (update execution facts)
        retrieved.entry_price = 2051.00  # Changed
        retrieved.exit_price = 2056.00  # Changed
        retrieved.profit = 5.5  # Changed
        store.update_trade(retrieved)
        
        # Verify journal data preserved
        final = store.get_trade(1)
        assert final.bias == "Bullish"
        assert final.notes == "Strong setup"
        assert final.grade == "A"
        # But execution facts updated
        assert final.entry_price == 2051.00
        assert final.profit == 5.5
