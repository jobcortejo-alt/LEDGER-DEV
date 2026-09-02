"""Command-line interface."""

import argparse
from datetime import datetime
from pathlib import Path
from ledger.store import Store
from ledger.models import Trade
from ledger.stats import StatsEngine
from ledger.mt5_source import MT5Source
import random


def cmd_sync(args):
    """Sync from MT5."""
    store = Store(args.db)
    mt5 = MT5Source()
    
    if not mt5.is_available():
        print("MetaTrader 5 not available")
        return
    
    deals = mt5.get_closed_deals(args.days or 90)
    trades = mt5.aggregate_positions(deals)
    
    synced = 0
    for trade in trades:
        try:
            existing = store.get_trade(trade.position_id)
            if existing:
                # Update execution facts
                existing.entry_price = trade.entry_price
                existing.exit_price = trade.exit_price
                existing.volume = trade.volume
                existing.commission = trade.commission
                existing.swap = trade.swap
                existing.profit = trade.profit
                existing.synced_at = datetime.utcnow()
                existing.calculate_r()
                store.update_trade(existing)
            else:
                store.insert_trade(trade)
                synced += 1
        except Exception as e:
            print(f"Error: {e}")
    
    print(f"Synced {synced} new trades")


def cmd_stats(args):
    """Print statistics report."""
    store = Store(args.db)
    trades = store.list_trades(exclude_backtest=True)
    
    engine = StatsEngine()
    report = engine.analyse(trades)
    
    print(f"\nStatistics Report")
    print(f"="*60)
    print(f"Total trades: {report.total_trades}")
    print(f"Wins: {report.win_count}, Losses: {report.loss_count}")
    print(f"Win rate: {report.win_rate:.1%}")
    print(f"Mean R: {report.mean_r:.2f} [{report.mean_r_ci_lower:.2f}, {report.mean_r_ci_upper:.2f}]")
    
    if args.verbose:
        print(f"\nCuts:")
        print(f"-"*60)
        for cut in report.cuts:
            if cut.count >= 30:
                verdict = cut.bh_verdict
                p_str = f"p={cut.p_value:.4f}" if cut.p_value else "p=N/A"
                print(f"{cut.cut_name} {cut.group_name}: R={cut.mean_r:.2f} [{cut.ci_lower:.2f}, {cut.ci_upper:.2f}] ({cut.count}) {p_str} {verdict}")
        
        print(f"\nUnderpowered (n<30):")
        for cut in report.cuts:
            if cut.count < 30:
                print(f"{cut.cut_name} {cut.group_name}: n={cut.count}")


def cmd_demo(args):
    """Generate demo data with planted effects."""
    store = Store(args.db)
    n = args.n or 320
    
    print(f"Generating {n} demo trades...")
    
    # Clear existing
    existing = store.list_trades(exclude_backtest=False)
    for t in existing:
        store.delete_trade(t.position_id)
    
    # Generate trades
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    
    ny_tz = ZoneInfo("America/New_York")
    now = datetime.now(tz=ny_tz)
    
    for i in range(n):
        # Random entry time
        days_back = random.randint(0, 90)
        entry_time = now - timedelta(days=days_back, hours=random.randint(0, 23))
        exit_time = entry_time + timedelta(hours=random.randint(1, 24))
        
        # Direction
        direction = random.choice(["BUY", "SELL"])
        
        # Entry/exit prices
        entry_price = 2000 + random.uniform(-50, 50)
        if direction == "BUY":
            exit_price = entry_price + random.uniform(-20, 20)
        else:
            exit_price = entry_price - random.uniform(-20, 20)
        
        # Stop loss
        if direction == "BUY":
            stop_loss = entry_price - random.uniform(5, 15)
        else:
            stop_loss = entry_price + random.uniform(5, 15)
        
        # Risk
        risk = abs(entry_price - stop_loss)
        profit = (exit_price - entry_price) if direction == "BUY" else (entry_price - exit_price)
        
        # Planted effect 1: broken rules cost ~0.7R
        has_broken_rule = random.random() < 0.15
        if has_broken_rule:
            r_target = -0.7
            profit = risk * r_target + random.uniform(-0.1, 0.1) * risk
        else:
            r_target = 0.1
            profit = risk * r_target + random.uniform(-0.2, 0.2) * risk
        
        # Planted effect 2: complete narrative adds ~0.4R
        has_all_premises = random.random() < 0.15
        if has_all_premises:
            r_target += 0.4
            profit = risk * r_target + random.uniform(-0.1, 0.1) * risk
        
        # Randomise the rest
        grade = random.choice(["A", "B", "C", "D", None])
        premises = list(range(7)) if has_all_premises else random.sample(range(7), random.randint(0, 6))
        
        trade = Trade(
            position_id=10000 + i,
            symbol="XAUUSD",
            entry_time=entry_time,
            entry_price=entry_price,
            exit_time=exit_time,
            exit_price=exit_price,
            volume=random.uniform(0.1, 5.0),
            commission=random.uniform(0, 5),
            swap=random.uniform(-10, 10),
            profit=profit,
            direction=direction,
            source="EA LIVE",
            stop_loss=stop_loss,
            grade=grade,
            premises_met=premises,
            tags=["BROKEN RULE"] if has_broken_rule else [],
        )
        
        # Classify killzones/macros
        from ledger.utils import classify_killzone, classify_macro
        trade.ny_killzone = classify_killzone(entry_time)
        trade.ny_macro = classify_macro(entry_time)
        trade.broker_killzone = "Outside"
        trade.broker_macro = "European"
        
        trade.calculate_r()
        store.insert_trade(trade)
    
    print(f"Generated {n} trades")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Ledger CLI")
    parser.add_argument("--db", default="ledger.db", help="Database path")
    
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # sync
    sync_parser = subparsers.add_parser("sync", help="Sync from MT5")
    sync_parser.add_argument("--days", type=int, help="Days back to sync")
    sync_parser.set_defaults(func=cmd_sync)
    
    # stats
    stats_parser = subparsers.add_parser("stats", help="Print statistics")
    stats_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    stats_parser.set_defaults(func=cmd_stats)
    
    # demo
    demo_parser = subparsers.add_parser("demo", help="Generate demo data")
    demo_parser.add_argument("-n", type=int, help="Number of trades")
    demo_parser.set_defaults(func=cmd_demo)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()
