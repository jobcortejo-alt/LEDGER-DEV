"""Database storage for trades."""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from ledger.models import Trade, Direction
import json

class Store:
    """SQLite-based trade storage."""
    
    def __init__(self, db_path: str):
        """Initialize store with database path."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    
    def _init_schema(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    position_id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    entry_time TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_time TEXT NOT NULL,
                    exit_price REAL NOT NULL,
                    volume REAL NOT NULL,
                    commission REAL NOT NULL,
                    swap REAL NOT NULL,
                    profit REAL NOT NULL,
                    direction TEXT NOT NULL,
                    source TEXT DEFAULT 'EA LIVE',
                    stop_loss REAL,
                    take_profit REAL,
                    ny_killzone TEXT,
                    macro_session TEXT,
                    bias TEXT,
                    notes TEXT,
                    grade TEXT,
                    tags TEXT DEFAULT '[]',
                    premises_met TEXT DEFAULT '[]',
                    rule_breaks TEXT DEFAULT '[]',
                    r_value REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def insert_trade(self, trade: Trade) -> int:
        """Insert a trade. Returns position_id."""
        errors = trade.validate()
        if errors:
            raise ValueError(f"Invalid trade: {', '.join(errors)}")
        
        trade.calculate_r()
        
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    INSERT INTO trades (
                        position_id, symbol, entry_time, entry_price,
                        exit_time, exit_price, volume, commission, swap,
                        profit, direction, source, stop_loss, take_profit,
                        ny_killzone, macro_session, bias, notes, grade,
                        tags, premises_met, rule_breaks, r_value
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.position_id, trade.symbol,
                    trade.entry_time.isoformat(), trade.entry_price,
                    trade.exit_time.isoformat(), trade.exit_price,
                    trade.volume, trade.commission, trade.swap,
                    trade.profit, trade.direction.value, trade.source,
                    trade.stop_loss, trade.take_profit,
                    trade.ny_killzone, trade.macro_session,
                    trade.bias, trade.notes, trade.grade,
                    json.dumps(trade.tags),
                    json.dumps(trade.premises_met),
                    json.dumps(trade.rule_breaks),
                    trade.r_value
                ))
                conn.commit()
            except sqlite3.IntegrityError:
                raise ValueError(f"Trade with position_id {trade.position_id} already exists")
        
        return trade.position_id
    
    def get_trade(self, position_id: int) -> Optional[Trade]:
        """Get a trade by position_id."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM trades WHERE position_id = ?",
                (position_id,)
            )
            row = cursor.fetchone()
        
        if not row:
            return None
        
        return self._row_to_trade(row)
    
    def update_trade(self, trade: Trade):
        """Update an existing trade."""
        errors = trade.validate()
        if errors:
            raise ValueError(f"Invalid trade: {', '.join(errors)}")
        
        trade.calculate_r()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE trades SET
                    entry_price = ?, exit_price = ?, volume = ?,
                    commission = ?, swap = ?, profit = ?,
                    stop_loss = ?, take_profit = ?,
                    ny_killzone = ?, macro_session = ?,
                    bias = ?, notes = ?, grade = ?,
                    tags = ?, premises_met = ?, rule_breaks = ?,
                    r_value = ?, updated_at = CURRENT_TIMESTAMP
                WHERE position_id = ?
            """, (
                trade.entry_price, trade.exit_price, trade.volume,
                trade.commission, trade.swap, trade.profit,
                trade.stop_loss, trade.take_profit,
                trade.ny_killzone, trade.macro_session,
                trade.bias, trade.notes, trade.grade,
                json.dumps(trade.tags),
                json.dumps(trade.premises_met),
                json.dumps(trade.rule_breaks),
                trade.r_value,
                trade.position_id
            ))
            conn.commit()
    
    def delete_trade(self, position_id: int):
        """Delete a trade."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM trades WHERE position_id = ?", (position_id,))
            conn.commit()
    
    def list_trades(self, exclude_backtest: bool = True) -> List[Trade]:
        """List all trades, optionally excluding backtests."""
        query = "SELECT * FROM trades"
        params = []
        
        if exclude_backtest:
            query += " WHERE source != ?"
            params.append("EA BACKTEST")
        
        query += " ORDER BY entry_time"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
        
        return [self._row_to_trade(row) for row in rows]
    
    def count_trades(self, exclude_backtest: bool = True) -> int:
        """Count trades."""
        query = "SELECT COUNT(*) FROM trades"
        params = []
        
        if exclude_backtest:
            query += " WHERE source != ?"
            params.append("EA BACKTEST")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            count = cursor.fetchone()[0]
        
        return count
    
    def _row_to_trade(self, row) -> Trade:
        """Convert database row to Trade object."""
        return Trade(
            position_id=row["position_id"],
            symbol=row["symbol"],
            entry_time=datetime.fromisoformat(row["entry_time"]),
            entry_price=row["entry_price"],
            exit_time=datetime.fromisoformat(row["exit_time"]),
            exit_price=row["exit_price"],
            volume=row["volume"],
            commission=row["commission"],
            swap=row["swap"],
            profit=row["profit"],
            direction=Direction(row["direction"]),
            source=row["source"],
            stop_loss=row["stop_loss"],
            take_profit=row["take_profit"],
            ny_killzone=row["ny_killzone"],
            macro_session=row["macro_session"],
            bias=row["bias"],
            notes=row["notes"],
            grade=row["grade"],
            tags=json.loads(row["tags"]),
            premises_met=json.loads(row["premises_met"]),
            rule_breaks=json.loads(row["rule_breaks"]),
            r_value=row["r_value"],
        )
