"""FastAPI HTTP server for Ledger."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from ledger.config import Config
from ledger.store import Store
from ledger.models import Trade
from ledger.stats import StatsEngine
from ledger.mt5_source import MT5Source
from ledger.notion import NotionSync
from ledger.ai import Analyst

# Load config
cfg = Config()

# Initialize components
app = FastAPI(title="Ledger", version="4.0.0")
store = Store(cfg.db_path)
stats_engine = StatsEngine()
mt5 = MT5Source(cfg.broker_tz)
notion = NotionSync(cfg.notion_token, cfg.notion_database_id) if cfg.notion_token else None
analyst = Analyst(cfg.anthropic_api_key) if cfg.anthropic_api_key else None

# CORS middleware (127.0.0.1 only, but allow browser requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:*", "http://localhost:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Trade Endpoints
# ============================================================================

@app.get("/api/trades")
def list_trades(exclude_backtest: bool = True):
    """List all trades."""
    trades = store.list_trades(exclude_backtest=exclude_backtest)
    return [
        {
            **t.to_dict(),
            "r_value": t.r_value,
            "is_win": t.is_win(),
            "is_loss": t.is_loss(),
        }
        for t in trades
    ]


@app.get("/api/trades/{position_id}")
def get_trade(position_id: int):
    """Fetch a single trade by position ID."""
    trade = store.get_trade(position_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade.to_dict()


@app.post("/api/trades")
def create_trade(trade_data: dict):
    """Create a new trade."""
    try:
        trade = Trade(**trade_data)
        errors = trade.validate()
        if errors:
            raise HTTPException(status_code=400, detail="\n".join(errors))
        
        trade_id = store.insert_trade(trade)
        return {"id": trade_id, **trade.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.patch("/api/trades/{position_id}")
def update_trade(position_id: int, updates: dict):
    """Update a trade (journal fields only)."""
    trade = store.get_trade(position_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    # Only allow journal fields to be updated
    journal_fields = ["bias", "read", "notes", "grade", "tags", "premises_met", "liq_swept", "stop_loss", "target"]
    for field in journal_fields:
        if field in updates:
            setattr(trade, field, updates[field])
    
    trade.edited = True
    trade.calculate_r()
    store.update_trade(trade)
    
    return trade.to_dict()


@app.delete("/api/trades/{position_id}")
def delete_trade(position_id: int):
    """Delete a trade."""
    trade = store.get_trade(position_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    store.delete_trade(position_id)
    return {"deleted": position_id}


# ============================================================================
# Statistics Endpoints
# ============================================================================

@app.get("/api/stats")
def get_stats():
    """Get full statistics report."""
    trades = store.list_trades(exclude_backtest=True)
    report = stats_engine.analyse(trades)
    return report.to_dict()


@app.get("/api/stats/dashboard")
def get_dashboard():
    """Get dashboard summary (current month)."""
    now = datetime.utcnow()
    trades = store.list_trades_by_month(now.year, now.month, exclude_backtest=True)
    
    if not trades:
        return {
            "month": f"{now.year}-{now.month:02d}",
            "total_trades": 0,
            "win_count": 0,
            "win_rate": 0.0,
            "mean_r": 0.0,
            "streak": 0,
        }
    
    # Calculate streak
    streak = 0
    for trade in reversed(trades):
        if trade.is_win():
            streak += 1
        else:
            break
    
    win_count = sum(1 for t in trades if t.is_win())
    mean_r = sum(t.r_value for t in trades if t.r_value) / len([t for t in trades if t.r_value]) if any(t.r_value for t in trades) else 0.0
    
    return {
        "month": f"{now.year}-{now.month:02d}",
        "total_trades": len(trades),
        "win_count": win_count,
        "win_rate": win_count / len(trades),
        "mean_r": mean_r,
        "streak": streak,
    }


@app.get("/api/stats/calendar/{year}/{month}")
def get_calendar(year: int, month: int):
    """Get calendar heatmap for a month."""
    trades = store.list_trades_by_month(year, month, exclude_backtest=True)
    
    # Group by day
    by_day = {}
    for trade in trades:
        day = trade.entry_time.day
        if day not in by_day:
            by_day[day] = {"count": 0, "wins": 0, "mean_r": 0.0}
        by_day[day]["count"] += 1
        if trade.is_win():
            by_day[day]["wins"] += 1
        if trade.r_value:
            by_day[day]["mean_r"] += trade.r_value
    
    # Compute means
    for day in by_day:
        if by_day[day]["count"] > 0:
            by_day[day]["mean_r"] /= by_day[day]["count"]
    
    return {"year": year, "month": month, "days": by_day}


# ============================================================================
# MT5 Integration
# ============================================================================

@app.post("/api/mt5/sync")
def sync_mt5():
    """Trigger MT5 sync."""
    if not mt5.is_available():
        raise HTTPException(status_code=503, detail="MetaTrader 5 not available")
    
    try:
        deals = mt5.get_closed_deals(cfg.sync_days)
        trades = mt5.aggregate_positions(deals)
        
        synced = 0
        updated = 0
        errors = 0
        
        for trade in trades:
            existing = store.get_trade(trade.position_id)
            if existing:
                # Update execution facts only
                existing.entry_price = trade.entry_price
                existing.exit_price = trade.exit_price
                existing.volume = trade.volume
                existing.commission = trade.commission
                existing.swap = trade.swap
                existing.profit = trade.profit
                existing.synced_at = datetime.utcnow()
                existing.calculate_r()
                store.update_trade(existing)
                updated += 1
            else:
                try:
                    store.insert_trade(trade)
                    synced += 1
                except Exception as e:
                    errors += 1
        
        return {
            "synced": synced,
            "updated": updated,
            "errors": errors,
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Notion Integration
# ============================================================================

@app.post("/api/notion/pull")
def pull_notion():
    """Pull from Notion."""
    if not notion or not notion.is_configured():
        raise HTTPException(status_code=503, detail="Notion not configured")
    
    try:
        trades = notion.pull()
        synced = 0
        for trade in trades:
            existing = store.get_trade(trade.position_id)
            if not existing:
                store.insert_trade(trade)
                synced += 1
        return {"pulled": synced}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/notion/push")
def push_notion():
    """Push to Notion."""
    if not notion or not notion.is_configured():
        raise HTTPException(status_code=503, detail="Notion not configured")
    
    try:
        trades = store.list_trades(exclude_backtest=False)
        notion.push(trades)
        return {"pushed": len(trades)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AI Analyst
# ============================================================================

@app.post("/api/analyse")
def analyse():
    """Request AI analysis."""
    if not analyst or not analyst.is_configured():
        raise HTTPException(status_code=503, detail="Anthropic API not configured")
    
    try:
        trades = store.list_trades(exclude_backtest=True)
        report = stats_engine.analyse(trades)
        analysis = analyst.analyse(report)
        return {"analysis": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Configuration
# ============================================================================

@app.get("/api/config")
def get_config():
    """Get application config (no secrets)."""
    return cfg.to_dict()


# ============================================================================
# UI
# ============================================================================

# Serve static files
web_dir = Path(__file__).parent.parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=web_dir), name="static")
    
    @app.get("/")
    def root():
        """Serve index.html."""
        index = web_dir / "index.html"
        if index.exists():
            return FileResponse(index)
        return {"message": "Ledger API"}
