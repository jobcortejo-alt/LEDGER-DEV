"""Trade model and R arithmetic."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import math


@dataclass
class Trade:
    """A single aggregated trade position."""
    
    # Broker execution facts (never overwritten on sync)
    position_id: int
    symbol: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    volume: float
    commission: float
    swap: float
    profit: float
    direction: str  # "BUY" or "SELL"
    source: str = "EA LIVE"  # "EA LIVE", "EA BACKTEST", "MANUAL"
    
    # Calculated fields
    broker_killzone: str = "Outside"
    broker_macro: str = "European"
    ny_killzone: str = "Outside"
    ny_macro: str = "European"
    r_value: Optional[float] = None
    
    # Trader journal data (preserved on re-sync)
    bias: Optional[str] = None
    read: Optional[str] = None
    notes: Optional[str] = None
    grade: Optional[str] = None  # "A", "B", "C", "D"
    tags: List[str] = field(default_factory=list)
    premises_met: List[int] = field(default_factory=list)  # Indices 0-6
    liq_swept: List[str] = field(default_factory=lambda: ["NONE"])
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    edited: bool = False
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    synced_at: Optional[datetime] = None
    
    def calculate_r(self) -> Optional[float]:
        """
        Calculate R (risk/reward ratio).
        
        BUY:  R = Profit / (Entry - Stop)
        SELL: R = Profit / (Stop - Entry)
        
        Returns None if stop_loss is not set.
        """
        if self.stop_loss is None:
            return None
        
        if self.direction.upper() == "BUY":
            risk = self.entry_price - self.stop_loss
        elif self.direction.upper() == "SELL":
            risk = self.stop_loss - self.entry_price
        else:
            return None
        
        if risk <= 0:
            return None
        
        r = self.profit / risk
        self.r_value = r
        return r
    
    def is_backtest(self) -> bool:
        """Return True if this trade is from backtesting."""
        return self.source == "EA BACKTEST"
    
    def has_complete_premises(self) -> bool:
        """Return True if all 7 premises are met."""
        return len(self.premises_met) == 7
    
    def premise_count(self) -> int:
        """Return count of met premises (0-7)."""
        return len(self.premises_met)
    
    def is_win(self) -> bool:
        """Return True if profit > 0."""
        return self.profit > 0
    
    def is_loss(self) -> bool:
        """Return True if profit <= 0."""
        return self.profit <= 0
    
    def duration_hours(self) -> float:
        """Return trade duration in hours."""
        delta = self.exit_time - self.entry_time
        return delta.total_seconds() / 3600
    
    def validate(self) -> List[str]:
        """
        Validate trade integrity.
        
        Returns list of error messages (empty if valid).
        """
        errors = []
        
        if self.volume <= 0:
            errors.append("Volume must be positive")
        
        if self.entry_time >= self.exit_time:
            errors.append("Exit time must be after entry time")
        
        if self.direction.upper() not in ("BUY", "SELL"):
            errors.append("Direction must be 'BUY' or 'SELL'")
        
        if self.entry_price <= 0:
            errors.append("Entry price must be positive")
        
        if self.exit_price <= 0:
            errors.append("Exit price must be positive")
        
        if self.stop_loss is not None:
            if self.direction.upper() == "BUY" and self.stop_loss >= self.entry_price:
                errors.append("BUY stop loss must be below entry price")
            elif self.direction.upper() == "SELL" and self.stop_loss <= self.entry_price:
                errors.append("SELL stop loss must be above entry price")
        
        if self.grade is not None and self.grade not in ("A", "B", "C", "D"):
            errors.append("Grade must be A, B, C, or D")
        
        if not (0 <= len(self.premises_met) <= 7):
            errors.append("Premises met must be between 0 and 7")
        
        return errors
    
    def to_dict(self) -> dict:
        """Convert trade to dictionary for JSON serialization."""
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "entry_time": self.entry_time.isoformat(),
            "entry_price": self.entry_price,
            "exit_time": self.exit_time.isoformat(),
            "exit_price": self.exit_price,
            "volume": self.volume,
            "commission": self.commission,
            "swap": self.swap,
            "profit": self.profit,
            "direction": self.direction,
            "source": self.source,
            "broker_killzone": self.broker_killzone,
            "broker_macro": self.broker_macro,
            "ny_killzone": self.ny_killzone,
            "ny_macro": self.ny_macro,
            "r_value": self.r_value,
            "bias": self.bias,
            "read": self.read,
            "notes": self.notes,
            "grade": self.grade,
            "tags": self.tags,
            "premises_met": self.premises_met,
            "liq_swept": self.liq_swept,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "edited": self.edited,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "synced_at": self.synced_at.isoformat() if self.synced_at else None,
        }


def aggregate_deals(deals: List[dict]) -> Trade:
    """
    Aggregate multiple MT5 deals (partial closes) into a single Trade.
    
    Args:
        deals: List of deal dicts, each with:
            position_id, symbol, direction, entry_time, entry_price,
            exit_time, exit_price, volume, commission, swap, profit, source
    
    Returns:
        Single aggregated Trade with volume-weighted prices.
    """
    if not deals:
        raise ValueError("Cannot aggregate empty deal list")
    
    # Verify all deals share same position_id
    position_id = deals[0]["position_id"]
    if not all(d["position_id"] == position_id for d in deals):
        raise ValueError("All deals must share same position_id")
    
    # Sort by time
    deals = sorted(deals, key=lambda d: d["entry_time"])
    
    # Extract opening deal (first)
    open_deal = deals[0]
    
    # Aggregate closes
    total_volume = sum(d.get("volume", 0) for d in deals)
    weighted_entry = sum(d.get("entry_price", 0) * d.get("volume", 0) for d in deals) / total_volume if total_volume > 0 else 0
    weighted_exit = sum(d.get("exit_price", 0) * d.get("volume", 0) for d in deals) / total_volume if total_volume > 0 else 0
    
    summed_commission = sum(d.get("commission", 0) for d in deals)
    summed_swap = sum(d.get("swap", 0) for d in deals)
    summed_profit = sum(d.get("profit", 0) for d in deals)
    
    # Use first entry time and last exit time
    entry_time = open_deal["entry_time"]
    exit_time = deals[-1]["exit_time"]
    
    trade = Trade(
        position_id=position_id,
        symbol=open_deal["symbol"],
        entry_time=entry_time,
        entry_price=weighted_entry,
        exit_time=exit_time,
        exit_price=weighted_exit,
        volume=total_volume,
        commission=summed_commission,
        swap=summed_swap,
        profit=summed_profit,
        direction=open_deal.get("direction", "BUY"),
        source=open_deal.get("source", "EA LIVE"),
    )
    
    return trade
