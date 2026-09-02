#!/usr/bin/env python3
"""Main entry point for Ledger application."""

import sys
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import webview
from ledger.api import create_app
from ledger.config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ledger.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Start Ledger application."""
    try:
        config = Config.load()
        app = create_app(config)
        
        # Try native window first, fall back to browser
        try:
            api_url = f"http://localhost:{config.port}"
            window = webview.create_window('Ledger', api_url)
            webview.start(debug=False)
        except Exception as e:
            logger.warning(f"Native window failed: {e}, falling back to browser")
            uvicorn.run(app, host="localhost", port=config.port)
    except Exception as e:
        logger.error(f"Failed to start Ledger: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
