"""Configuration management."""

import os
from pathlib import Path
from dataclasses import dataclass
import tomllib
import json
from typing import Optional

@dataclass
class Config:
    """Application configuration."""
    db: str = "ledger.db"
    port: int = 8756
    open_browser: bool = True
    broker_tz: str = "Europe/Athens"
    default_source: str = "EA LIVE"
    sync_days: int = 90
    mt5_login: str = ""
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_terminal_path: str = ""
    notion_token: str = ""
    notion_database_id: str = ""
    notion_version: str = "2022-06-28"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    
    @classmethod
    def load(cls, config_file: Optional[str] = None) -> 'Config':
        """Load configuration from file."""
        if config_file is None:
            config_file = "config.toml"
        
        if not Path(config_file).exists():
            return cls()  # Return defaults
        
        try:
            with open(config_file, 'rb') as f:
                data = tomllib.load(f)
            
            config_dict = {}
            if 'app' in data:
                config_dict.update({
                    'db': data['app'].get('db', 'ledger.db'),
                    'port': data['app'].get('port', 8756),
                    'open_browser': data['app'].get('open_browser', True),
                })
            if 'mt5' in data:
                config_dict.update({
                    'broker_tz': data['mt5'].get('broker_tz', 'Europe/Athens'),
                    'default_source': data['mt5'].get('default_source', 'EA LIVE'),
                    'sync_days': data['mt5'].get('sync_days', 90),
                    'mt5_login': data['mt5'].get('login', ''),
                    'mt5_password': data['mt5'].get('password', ''),
                    'mt5_server': data['mt5'].get('server', ''),
                    'mt5_terminal_path': data['mt5'].get('terminal_path', ''),
                })
            if 'notion' in data:
                config_dict.update({
                    'notion_token': data['notion'].get('token', ''),
                    'notion_database_id': data['notion'].get('database_id', ''),
                    'notion_version': data['notion'].get('version', '2022-06-28'),
                })
            if 'anthropic' in data:
                config_dict.update({
                    'anthropic_api_key': data['anthropic'].get('api_key', ''),
                    'anthropic_model': data['anthropic'].get('model', 'claude-sonnet-4-5'),
                })
            
            return cls(**config_dict)
        except Exception as e:
            raise RuntimeError(f"Failed to load config: {e}")
