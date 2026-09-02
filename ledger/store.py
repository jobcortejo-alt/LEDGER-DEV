"""SQLite database persistence and schema management."""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple
from ledger.models import Trade


class Store:
    """SQLite database for trades."""
    
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_schema(self) -> None:
        """Initialize database schema."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Create trades table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            position_id INTEGER UNIQUE NOT NULL,
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
            source TEXT NOT NULL DEFAULT 'EA LIVE',
            
            broker_killzone TEXT DEFAULT 'Outside',
            broker_macro TEXT DEFAULT 'European',
            ny_killzone TEXT DEFAULT 'Outside',
            ny_macro TEXT DEFAULT 'European',
            r_value REAL,
            
            bias TEXT,
            read TEXT,
            notes TEXT,
            grade TEXT,
            tags TEXT DEFAULT '[]',
            premises_met TEXT DEFAULT '[]',
            liq_swept TEXT DEFAULT '["NONE"]',
            stop_loss REAL,
            target REAL,
            edited INTEGER DEFAULT 0,
            
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            synced_at TEXT
        )
        """)
        
        # Create indices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_position_id ON trades(position_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON trades(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entry_time ON trades(entry_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_exit_time ON trades(exit_time)")
        
        conn.commit()
        conn.close()
    
    def insert_trade(self, trade: Trade) -> int:
        """
        Insert a trade. Returns the database id.
        
        Raises ValueError if position_id already exists.
        """
        import json
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            INSERT INTO trades (
                position_id, symbol, entry_time, entry_price,
                exit_time, exit_price, volume, commission, swap, profit,
                direction, source, broker_killzone, broker_macro,
                ny_killzone, ny_macro, r_value,
                bias, read, notes, grade, tags, premises_met, liq_swept,
                stop_loss, target, edited, created_at, updated_at, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.position_id,
                trade.symbol,
                trade.entry_time.isoformat(),
                trade.entry_price,
                trade.exit_time.isoformat(),
                trade.exit_price,
                trade.volume,
                trade.commission,
                trade.swap,
                trade.profit,
                trade.direction,
                trade.source,
                trade.broker_killzone,
                trade.broker_macro,
                trade.ny_killzone,
                trade.ny_macro,
                trade.r_value,
                trade.bias,
                trade.read,
                trade.notes,
                trade.grade,
                json.dumps(trade.tags),
                json.dumps(trade.premises_met),
                json.dumps(trade.liq_swept),
                trade.stop_loss,
                trade.target,
                int(trade.edited),
                trade.created_at.isoformat(),
                trade.updated_at.isoformat(),
                trade.synced_at.isoformat() if trade.synced_at else None,
            ))
            
            trade_id = cursor.lastrowid
            conn.commit()
            return trade_id
        
        except sqlite3.IntegrityError as e:
            conn.close()
            raise ValueError(f"Duplicate position_id: {trade.position_id}") from e
        
        finally:
            conn.close()
    
    def get_trade(self, position_id: int) -> Optional[Trade]:
        """Fetch trade by position_id."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM trades WHERE position_id = ?", (position_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._row_to_trade(row)
    
    def update_trade(self, trade: Trade) -> None:
        """Update an existing trade (journal fields only)."""
        import json
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        trade.updated_at = datetime.utcnow()
        
        cursor.execute("""
        UPDATE trades SET
            bias = ?, read = ?, notes = ?, grade = ?,
            tags = ?, premises_met = ?, liq_swept = ?,
            stop_loss = ?, target = ?, edited = ?,
            r_value = ?, updated_at = ?
        WHERE position_id = ?
        """, (
            trade.bias,
            trade.read,
            trade.notes,
            trade.grade,
            json.dumps(trade.tags),
            json.dumps(trade.premises_met),
            json.dumps(trade.liq_swept),
            trade.stop_loss,
            trade.target,
            int(trade.edited),
            trade.r_value,
            trade.updated_at.isoformat(),
            trade.position_id,
        ))
        
        conn.commit()
        conn.close()
    
    def delete_trade(self, position_id: int) -> None:
        """Delete a trade by position_id."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM trades WHERE position_id = ?", (position_id,))
        conn.commit()
        conn.close()
    
    def list_trades(self, exclude_backtest: bool = True) -> List[Trade]:
        """List all trades, optionally excluding backtests."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        if exclude_backtest:
            cursor.execute("SELECT * FROM trades WHERE source != 'EA BACKTEST' ORDER BY entry_time")
        else:
            cursor.execute("SELECT * FROM trades ORDER BY entry_time")
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_trade(row) for row in rows]
    
    def list_trades_by_month(self, year: int, month: int, exclude_backtest: bool = True) -> List[Trade]:
        """List trades for a specific month."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Month boundaries (rough, in UTC)
        from datetime import datetime
        start = datetime(year, month, 1).isoformat()
        if month == 12:
            end = datetime(year + 1, 1, 1).isoformat()
        else:
            end = datetime(year, month + 1, 1).isoformat()
        
        if exclude_backtest:
            cursor.execute("""
            SELECT * FROM trades
            WHERE source != 'EA BACKTEST' AND entry_time >= ? AND entry_time < ?
            ORDER BY entry_time
            """, (start, end))
        else:
            cursor.execute("""
            SELECT * FROM trades
            WHERE entry_time >= ? AND entry_time < ?
            ORDER BY entry_time
            """, (start, end))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_trade(row) for row in rows]
    
    def count_trades(self, exclude_backtest: bool = True) -> int:
        """Count total trades."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        if exclude_backtest:
            cursor.execute("SELECT COUNT(*) FROM trades WHERE source != 'EA BACKTEST'")
        else:
            cursor.execute("SELECT COUNT(*) FROM trades")
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    def _row_to_trade(self, row: sqlite3.Row) -> Trade:
        """Convert database row to Trade object."""
        import json
        
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
            direction=row["direction"],
            source=row["source"],
            broker_killzone=row["broker_killzone"],
            broker_macro=row["broker_macro"],
            ny_killzone=row["ny_killzone"],
            ny_macro=row["ny_macro"],
            r_value=row["r_value"],
            bias=row["bias"],
            read=row["read"],
            notes=row["notes"],
            grade=row["grade"],
            tags=json.loads(row["tags"] or "[]"),
            premises_met=json.loads(row["premises_met"] or "[]"),
            liq_swept=json.loads(row["liq_swept"] or '["NONE"]'),
            stop_loss=row["stop_loss"],
            target=row["target"],
            edited=bool(row["edited"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            synced_at=datetime.fromisoformat(row["synced_at"]) if row["synced_at"] else None,
        )
