"""Test configuration and fixtures."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from ledger.store import Store
from ledger.models import Trade


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield db_path


@pytest.fixture
def store(temp_db):
    """Create test store."""
    return Store(temp_db)


@pytest.fixture
def sample_trade():
    """Create a sample trade for testing."""
    return Trade(
        position_id=1,
        symbol="XAUUSD",
        entry_time=datetime(2026, 1, 1, 10, 0, 0),
        entry_price=2050.00,
        exit_time=datetime(2026, 1, 1, 12, 0, 0),
        exit_price=2055.00,
        volume=1.0,
        commission=1.0,
        swap=0.5,
        profit=4.5,
        direction="BUY",
        source="EA LIVE",
        stop_loss=2040.00,
    )
