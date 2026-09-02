"""MetaTrader 5 integration and position aggregation."""

from datetime import datetime
from typing import List, Dict, Optional
from ledger.models import Trade, aggregate_deals
from ledger.utils import classify_killzone, classify_macro, normalise_symbol


class MT5Source:
    """MetaTrader 5 connection and deal/position handling."""
    
    def __init__(self, broker_tz: str = "Europe/Athens"):
        self.broker_tz = broker_tz
        self.mt5 = None
        self._try_import_mt5()
    
    def _try_import_mt5(self) -> None:
        """Attempt to import MetaTrader5 module."""
        try:
            import MetaTrader5 as mt5
            self.mt5 = mt5
        except ImportError:
            self.mt5 = None
    
    def is_available(self) -> bool:
        """Return True if MT5 is available."""
        return self.mt5 is not None
    
    def get_closed_deals(self, days_back: int = 90) -> List[Dict]:
        """
        Fetch closed deals from MT5 terminal.
        
        Returns list of deal dicts, or empty list if MT5 not available/connected.
        """
        if not self.is_available():
            return []
        
        try:
            # Check if terminal is running
            if not self.mt5.initialize():
                return []
            
            # Fetch closed deals from history
            from datetime import datetime, timedelta
            from_date = datetime.now() - timedelta(days=days_back)
            
            deals = self.mt5.history_deals_get(from_date, datetime.now())
            self.mt5.shutdown()
            
            if not deals:
                return []
            
            # Convert to our format
            result = []
            for deal in deals:
                result.append({
                    "position_id": deal.position_id,
                    "symbol": normalise_symbol(deal.symbol),
                    "direction": "BUY" if deal.type in (0, 2) else "SELL",  # 0=BUY, 1=SELL, 2=BUY_LIMIT, etc
                    "entry_time": datetime.fromtimestamp(deal.time),
                    "entry_price": float(deal.price),
                    "exit_time": datetime.fromtimestamp(deal.time_msc / 1000) if hasattr(deal, 'time_msc') else datetime.fromtimestamp(deal.time),
                    "exit_price": float(deal.price),
                    "volume": float(deal.volume),
                    "commission": float(deal.commission),
                    "swap": float(deal.swap),
                    "profit": float(deal.profit),
                    "source": "EA LIVE",
                })
            
            return result
        
        except Exception as e:
            print(f"MT5 error: {e}")
            return []
    
    def aggregate_positions(self, deals: List[Dict]) -> List[Trade]:
        """
        Aggregate deals into logical positions and classify killzones/macros.
        
        Args:
            deals: List of deal dicts from MT5
        
        Returns:
            List of aggregated Trade objects
        """
        if not deals:
            return []
        
        # Group by position_id
        positions = {}
        for deal in deals:
            pos_id = deal["position_id"]
            if pos_id not in positions:
                positions[pos_id] = []
            positions[pos_id].append(deal)
        
        # Aggregate each position
        trades = []
        for pos_id, deals_list in positions.items():
            try:
                trade = aggregate_deals(deals_list)
                
                # Classify killzones and macros
                trade.ny_killzone = classify_killzone(trade.entry_time)
                trade.ny_macro = classify_macro(trade.entry_time)
                trade.broker_killzone = classify_killzone(trade.entry_time, reference_tz=self.broker_tz)
                trade.broker_macro = classify_macro(trade.entry_time, reference_tz=self.broker_tz)
                
                trades.append(trade)
            
            except Exception as e:
                print(f"Error aggregating position {pos_id}: {e}")
                continue
        
        return trades
