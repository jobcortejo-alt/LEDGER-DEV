"""Trade and statistics data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum
import math

class Direction(str, Enum):
    """Trade direction."""
    BUY = "BUY"
    SELL = "SELL"

class Verdict(str, Enum):
    """Statistical verdict."""
    HOLDING = "holding"
    SUSPICIOUS = "suspicious"
    TOO_LITTLE_DATA = "too little data"
    NOT_DEFINED = "NOT DEFINED"

@dataclass
class Trade:
    """Represents a single trade."""
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
    direction: Direction
    source: str = "EA LIVE"
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    ny_killzone: Optional[str] = None
    macro_session: Optional[str] = None
    bias: Optional[str] = None
    notes: Optional[str] = None
    grade: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    premises_met: List[int] = field(default_factory=list)
    rule_breaks: List[str] = field(default_factory=list)
    r_value: Optional[float] = None
    
    def validate(self) -> List[str]:
        """Validate trade data. Returns list of errors."""
        errors = []
        if self.volume <= 0:
            errors.append("Volume must be positive")
        if self.entry_time >= self.exit_time:
            errors.append("Entry time must be before exit time")
        if self.entry_price <= 0 or self.exit_price <= 0:
            errors.append("Prices must be positive")
        if self.stop_loss is not None and self.stop_loss <= 0:
            errors.append("Stop loss must be positive")
        return errors
    
    def calculate_r(self) -> Optional[float]:
        """Calculate R (risk/reward multiple). Returns None if no SL."""
        if self.stop_loss is None:
            self.r_value = None
            return None
        
        if self.direction == Direction.BUY:
            risk = self.entry_price - self.stop_loss
        else:  # SELL
            risk = self.stop_loss - self.entry_price
        
        if risk <= 0:
            self.r_value = None
            return None
        
        self.r_value = self.profit / risk
        return self.r_value
    
    def is_win(self) -> bool:
        """Check if trade is profitable."""
        return self.profit > 0
    
    def is_loss(self) -> bool:
        """Check if trade is a loss."""
        return self.profit < 0
    
    def is_backtest(self) -> bool:
        """Check if this is a backtest trade."""
        return self.source == "EA BACKTEST"
    
    def premise_count(self) -> int:
        """Return number of premises met."""
        return len(self.premises_met)
    
    def has_complete_premises(self) -> bool:
        """Check if all 7 premises were met."""
        return len(self.premises_met) == 7
    
    def has_broken_rules(self) -> bool:
        """Check if any rules were broken."""
        return len(self.rule_breaks) > 0

def aggregate_deals(deals: List[dict]) -> Trade:
    """Aggregate MT5 deals into a logical trade position.
    
    Handles partial closes and volume-weighted averaging.
    """
    if not deals:
        raise ValueError("No deals to aggregate")
    
    # Sort by time
    deals = sorted(deals, key=lambda x: x["entry_time"])
    
    position_id = deals[0]["position_id"]
    symbol = deals[0]["symbol"]
    direction = deals[0]["direction"]
    entry_time = deals[0]["entry_time"]
    entry_price = deals[0]["entry_price"]
    source = deals[0]["source"]
    
    total_volume = 0
    total_commission = 0
    total_swap = 0
    total_profit = 0
    weighted_exit_price = 0
    exit_time = None
    
    # Process all deals
    for deal in deals:
        total_volume += deal["volume"]
        total_commission += deal["commission"]
        total_swap += deal["swap"]
        total_profit += deal["profit"]
        weighted_exit_price += deal["exit_price"] * deal["volume"]
        if exit_time is None:
            exit_time = deal["exit_time"]
        else:
            exit_time = max(exit_time, deal["exit_time"])
    
    # Weighted average exit price
    if total_volume > 0:
        weighted_exit_price /= total_volume
    
    trade = Trade(
        position_id=position_id,
        symbol=symbol,
        entry_time=entry_time,
        entry_price=entry_price,
        exit_time=exit_time,
        exit_price=weighted_exit_price,
        volume=total_volume,
        commission=total_commission,
        swap=total_swap,
        profit=total_profit,
        direction=direction,
        source=source,
    )
    
    return trade

@dataclass
class StatisticsCut:
    """Results for a statistical cut."""
    cut_name: str
    cut_value: str
    trade_count: int
    win_count: int
    loss_count: int
    mean_r: float
    r_ci_lower: float
    r_ci_upper: float
    win_rate: float
    permutation_p: float
    bh_verdict: str
    rule_break_count: int = 0
    premise_incomplete_count: int = 0

@dataclass
class StatisticsReport:
    """Complete statistics report."""
    total_trades: int
    win_count: int
    loss_count: int
    win_rate: float
    mean_r: float
    mean_r_ci_lower: float
    mean_r_ci_upper: float
    cuts: List[StatisticsCut] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)
