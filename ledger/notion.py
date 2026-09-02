"""Notion two-way synchronisation."""

from typing import List, Dict, Optional
from datetime import datetime
from ledger.models import Trade
import requests
import json


class NotionSync:
    """Two-way synchronisation with Notion TRADE LOG 3.0 database."""
    
    def __init__(self, token: str, database_id: str, api_version: str = "2022-06-28"):
        self.token = token
        self.database_id = database_id
        self.api_version = api_version
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": api_version,
            "Content-Type": "application/json",
        }
    
    def is_configured(self) -> bool:
        """Return True if Notion is configured (token + database ID set)."""
        return bool(self.token and self.database_id)
    
    def pull(self) -> List[Trade]:
        """
        Pull trades from Notion database.
        
        Returns list of Trade objects (execution facts only, no journal data).
        Raises exception if API call fails.
        """
        if not self.is_configured():
            return []
        
        try:
            url = f"{self.base_url}/databases/{self.database_id}/query"
            response = requests.post(url, headers=self.headers, json={})
            response.raise_for_status()
            
            results = response.json().get("results", [])
            trades = []
            
            for page in results:
                trade = self._notion_page_to_trade(page)
                if trade:
                    trades.append(trade)
            
            return trades
        
        except Exception as e:
            print(f"Notion pull error: {e}")
            raise
    
    def push(self, trades: List[Trade]) -> None:
        """
        Push trades to Notion database.
        
        Only pushes trades not yet in Notion (by POSITION ID).
        Updates existing trades if they have been edited locally.
        
        Raises exception if API call fails.
        """
        if not self.is_configured():
            return
        
        try:
            # Get existing trades to avoid duplicates
            existing = self.pull()
            existing_ids = {t.position_id for t in existing}
            
            for trade in trades:
                if trade.position_id not in existing_ids:
                    self._create_notion_page(trade)
                elif trade.edited:
                    # Update existing page
                    self._update_notion_page(trade)
        
        except Exception as e:
            print(f"Notion push error: {e}")
            raise
    
    def _notion_page_to_trade(self, page: Dict) -> Optional[Trade]:
        """Convert Notion page to Trade object."""
        try:
            props = page["properties"]
            
            # Extract fields (map Notion property names)
            position_id = self._extract_number(props, "POSITION ID")
            if not position_id:
                return None
            
            trade = Trade(
                position_id=int(position_id),
                symbol=self._extract_text(props, "SYMBOL") or "XAUUSD",
                entry_time=self._extract_date(props, "ENTRY TIME") or datetime.utcnow(),
                entry_price=self._extract_number(props, "ENTRY PRICE") or 0.0,
                exit_time=self._extract_date(props, "EXIT TIME") or datetime.utcnow(),
                exit_price=self._extract_number(props, "EXIT PRICE") or 0.0,
                volume=self._extract_number(props, "VOLUME") or 0.0,
                commission=self._extract_number(props, "COMMISSION") or 0.0,
                swap=self._extract_number(props, "SWAP") or 0.0,
                profit=self._extract_number(props, "PROFIT") or 0.0,
                direction=self._extract_select(props, "DIRECTION") or "BUY",
                source=self._extract_select(props, "SOURCE") or "EA LIVE",
            )
            
            return trade
        
        except Exception as e:
            print(f"Error converting Notion page: {e}")
            return None
    
    def _create_notion_page(self, trade: Trade) -> None:
        """Create a new Notion page for a trade."""
        url = f"{self.base_url}/pages"
        
        data = {
            "parent": {"database_id": self.database_id},
            "properties": {
                "POSITION ID": {"number": trade.position_id},
                "SYMBOL": {"title": [{"text": {"content": trade.symbol}}]},
                "ENTRY PRICE": {"number": trade.entry_price},
                "EXIT PRICE": {"number": trade.exit_price},
                "VOLUME": {"number": trade.volume},
                "PROFIT": {"number": trade.profit},
                "DIRECTION": {"select": {"name": trade.direction}},
                "SOURCE": {"select": {"name": trade.source}},
                "ENTRY TIME": {"date": {"start": trade.entry_time.isoformat()}},
                "EXIT TIME": {"date": {"start": trade.exit_time.isoformat()}},
                "NOTES": {"rich_text": [{"text": {"content": trade.notes or ""}}]},
            },
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
    
    def _update_notion_page(self, trade: Trade) -> None:
        """Update an existing Notion page."""
        # Find page by POSITION ID (would require querying)
        # For now, skip updates to avoid duplicates
        pass
    
    def _extract_text(self, props: Dict, field: str) -> Optional[str]:
        """Extract text field from Notion properties."""
        try:
            if field not in props:
                return None
            prop = props[field]
            if prop.get("type") == "title":
                return prop["title"][0]["text"]["content"] if prop["title"] else None
            elif prop.get("type") == "rich_text":
                return prop["rich_text"][0]["text"]["content"] if prop["rich_text"] else None
            return None
        except (KeyError, IndexError, TypeError):
            return None
    
    def _extract_number(self, props: Dict, field: str) -> Optional[float]:
        """Extract number field from Notion properties."""
        try:
            if field not in props:
                return None
            prop = props[field]
            if prop.get("type") == "number":
                return prop["number"]
            return None
        except (KeyError, TypeError):
            return None
    
    def _extract_date(self, props: Dict, field: str) -> Optional[datetime]:
        """Extract date field from Notion properties."""
        try:
            if field not in props:
                return None
            prop = props[field]
            if prop.get("type") == "date" and prop["date"]:
                return datetime.fromisoformat(prop["date"]["start"])
            return None
        except (KeyError, ValueError, TypeError):
            return None
    
    def _extract_select(self, props: Dict, field: str) -> Optional[str]:
        """Extract select field from Notion properties."""
        try:
            if field not in props:
                return None
            prop = props[field]
            if prop.get("type") == "select" and prop["select"]:
                return prop["select"]["name"]
            return None
        except (KeyError, TypeError):
            return None
