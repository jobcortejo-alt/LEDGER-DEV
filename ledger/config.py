"""Configuration loading and validation."""

from pathlib import Path
from typing import Optional
import tomllib
import sys
import os


class Config:
    """Application configuration loaded from config.toml."""
    
    def __init__(self, path: Optional[Path] = None):
        if path is None:
            # Try config.toml in current directory or app directory
            if Path("config.toml").exists():
                path = Path("config.toml")
            elif Path(Path.home() / "Ledger" / "config.toml").exists():
                path = Path.home() / "Ledger" / "config.toml"
            else:
                path = Path("config.toml")
        
        self.path = path
        self.db_path: Path = Path("ledger.db")
        self.port: int = 8756
        self.open_browser: bool = True
        
        # MT5
        self.broker_tz: str = "Europe/Athens"
        self.default_source: str = "EA LIVE"
        self.sync_days: int = 90
        self.mt5_login: str = ""
        self.mt5_password: str = ""
        self.mt5_server: str = ""
        self.mt5_terminal_path: str = ""
        
        # Notion
        self.notion_token: str = ""
        self.notion_database_id: str = ""
        self.notion_version: str = "2022-06-28"
        
        # Anthropic
        self.anthropic_api_key: str = ""
        self.anthropic_model: str = "claude-sonnet-4-5"
        
        self.load()
    
    def load(self) -> None:
        """Load configuration from TOML file."""
        if not self.path.exists():
            return
        
        try:
            with open(self.path, "rb") as f:
                config = tomllib.load(f)
        except Exception as e:
            print(f"Error loading config: {e}", file=sys.stderr)
            return
        
        # App section
        if "app" in config:
            app = config["app"]
            if "db" in app:
                self.db_path = Path(app["db"])
            if "port" in app:
                self.port = int(app["port"])
            if "open_browser" in app:
                self.open_browser = bool(app["open_browser"])
        
        # MT5 section
        if "mt5" in config:
            mt5 = config["mt5"]
            if "broker_tz" in mt5:
                self.broker_tz = mt5["broker_tz"]
            if "default_source" in mt5:
                self.default_source = mt5["default_source"]
            if "sync_days" in mt5:
                self.sync_days = int(mt5["sync_days"])
            if "login" in mt5:
                self.mt5_login = mt5["login"] or ""
            if "password" in mt5:
                self.mt5_password = mt5["password"] or ""
            if "server" in mt5:
                self.mt5_server = mt5["server"] or ""
            if "terminal_path" in mt5:
                self.mt5_terminal_path = mt5["terminal_path"] or ""
        
        # Notion section
        if "notion" in config:
            notion = config["notion"]
            if "token" in notion:
                self.notion_token = notion["token"] or ""
            if "database_id" in notion:
                self.notion_database_id = notion["database_id"] or ""
            if "version" in notion:
                self.notion_version = notion["version"]
        
        # Anthropic section
        if "anthropic" in config:
            anthropic = config["anthropic"]
            if "api_key" in anthropic:
                self.anthropic_api_key = anthropic["api_key"] or ""
            if "model" in anthropic:
                self.anthropic_model = anthropic["model"]
    
    def to_dict(self) -> dict:
        """Return config as dictionary (excluding secrets)."""
        return {
            "db_path": str(self.db_path),
            "port": self.port,
            "open_browser": self.open_browser,
            "broker_tz": self.broker_tz,
            "default_source": self.default_source,
            "sync_days": self.sync_days,
            "notion_enabled": bool(self.notion_token),
            "anthropic_enabled": bool(self.anthropic_api_key),
        }
