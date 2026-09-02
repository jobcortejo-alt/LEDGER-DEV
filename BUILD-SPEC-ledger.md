# BUILD-SPEC-LEDGER v4

## Overview

Ledger v4 is a production-grade Windows desktop application for ICT (Inner Circle Trader) traders to journal and analyse closed trading positions. It reads directly from MetaTrader 5, synchronises with Notion, and provides statistically rigorous analysis using bootstrap confidence intervals and permutation testing.

The application runs entirely locally. Secrets are never exposed to the browser. Everything is encrypted in transit.

---

## Core Architecture

### Three Clocks

The application manages three independent time systems:

1. **Broker Server Time** – MT5 terminal's timezone (e.g. Europe/Athens, UTC+2/UTC+3)
   - Used to classify execution facts from MT5
   - Configured in `config.toml` as `broker_tz`

2. **New York Time (ICT Standard)** – The ICT trading framework standard
   - Used to classify killzones and macro periods
   - Always UTC-5 or UTC-4 depending on US daylight saving
   - **Killzones are assigned on the New York clock**

3. **User Local Time** – The trader's system timezone
   - Used for UI display, calendar grouping, and day/week/month boundaries
   - Extracted from `zoneinfo` on application start

All three are live, timezone-aware conversions. No hardcoded offsets.

### Seven ICT Premises

Every trade is assessed against seven premises (binary: present or not):

1. **Narrative** – Entry coincides with a higher-timeframe liquidity event or order block
2. **Optimism Bias** – Entry from a state of fear/pessimism (inverse: greed kills trades)
3. **Unconfirmed High** – Entry below the last unconfirmed daily/weekly high
4. **FVG/Imbalance** – Entry into a fair-value gap or market imbalance
5. **Discount/Premium** – Entry in relative discount (long) or premium (short)
6. **Premature Entry** – Entry before price has proven the intended direction *twice*
7. **Reversal Pattern** – Entry aligns with a reversal or continuation pattern

Trades with 4+ premises satisfied score higher reliability.

### R (Risk/Reward Ratio)

**Definition for BUY:**
```
Profit / (Entry Price - Stop Loss)
```

**Definition for SELL:**
```
Profit / (Stop Loss - Entry Price)
```

- **Positive R:** Profit exceeds risk. Good trade outcome.
- **Negative R:** Loss exceeds or equals risk. Poor trade outcome.
- **Missing Stop Loss:** Trade produces no R until stop is manually entered.
- **Partial Closes:** Volume-weighted across aggregated position.

Risk is always positive distance from entry to stop.

---

## Non-Negotiable Invariants

### 1. Backtest Isolation

- Trades where `source == "EA BACKTEST"` must **never** appear in:
  - Live statistics (win rate, mean R, etc.)
  - Charts or calendar displays
  - Calendar statistics (day-of-week, hour-of-day analysis)
  - AI analyst reports
  - Any finding or metric marked as "significant"

- Backtests can be viewed in the trade book *read-only* with visual distinction
- Backtest trades must not affect count of total trades
- Filtering is always: `source != "EA BACKTEST"` in all queries

### 2. Statistical Honesty

Every mean-R estimate, every percentile, every p-value must have bootstrap confidence intervals:

- **10,000-resample percentile bootstrap**
- **Seeded reproducibility** – same seed, same results
- **Permutation testing** for categorical cuts
  - Test each cut's best group vs. worst group
  - Use permutation (not t-test) because R distributions are heavy-tailed
- **Benjamini-Hochberg correction** at q = 0.10 across complete cut family
- **Never call a result significant** merely because it has the largest spread

### 3. Underpowered Groups

Groups with fewer than 30 trades:

- Can never be marked as "finding" or statistically significant
- Must carry verdict `too little data`
- P-values not published; confidence intervals shown with caveat

### 4. Position Aggregation

MT5 stores deals, not positions. Trades closed in multiple parts must aggregate:

- Group all deals by `position_id`
- Volume-weighted entry/exit prices
- Sum commission, swap, profit
- Collapse into single logical position
- Never re-disaggregate on re-sync

### 5. User-Owned Journal Data

Execution facts belong to broker; journal data belongs to trader.

**On sync (never overwrite):**
- `bias`, `read`, `notes`, `grade`, `tags`, `premises_*`, `liq_swept`

**Always update:**
- `entry_price`, `entry_time`, `exit_price`, `exit_time`, `volume`, `commission`, `swap`, `profit`

### 6. No Trading Signals

Application is historical review only. AI analyst **never:**

- Suggests trade direction
- Suggests entry/exit prices
- Predicts price or forecasts
- Overrides statistical verdicts
- Treats correlation as causation

### 7. MT5 Aggregation Guarantee

Partial closes never counted as independent trades. Test: 3-part close = 1 logical trade.

---

## Data Model

### Trade Record

```python
class Trade:
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
    source: str     # "EA LIVE", "EA BACKTEST", "MANUAL"
    
    # Calculated fields
    broker_killzone: str
    broker_macro: str
    ny_killzone: str
    ny_macro: str
    r_value: float | None
    
    # Trader journal data (preserved on re-sync)
    bias: str | None
    read: str | None
    notes: str | None
    grade: str | None  # "A", "B", "C", "D"
    tags: list[str]
    premises_met: list[int]
    liq_swept: list[str]
    stop_loss: float | None
    target: float | None
    edited: bool
    created_at: datetime
    updated_at: datetime
```

### Database (SQLite)

Single table: `trades`

Indexed on: `position_id`, `source`, `entry_time`, `exit_time`

---

## Killzone Classification

- **London Killzone:** 2:00–5:00 AM New York time
- **New York Killzone:** 7:00–10:00 AM New York time
- **Asian Killzone:** 7:00–10:00 PM New York time
- **Outside:** All other hours

Classification uses entry time in New York timezone.

**Macro (on entry time):**
- **European session:** 2:00 AM – 12:00 PM NY
- **American session:** 12:00 PM – 8:00 PM NY
- **Asian session:** 8:00 PM – 2:00 AM NY

---

## Statistics Engine

### Bootstrap Confidence Intervals

1. Resample 10,000 times with replacement (seeded)
2. Compute statistic for each resample
3. Extract percentiles [2.5%, 97.5%]
4. Return (lower, mean, upper)

### Permutation Testing

1. Compute observed difference (max_mean - min_mean)
2. Shuffle group labels 10,000 times
3. Count shuffles with difference >= observed
4. p-value = count / 10,000

### Benjamini-Hochberg Correction

Applied across all tested cuts (≈14 cuts):

1. Sort p-values
2. For each i: threshold = (i / N) * q, where q = 0.10
3. Find largest i where p[i] <= threshold
4. Mark all i <= that as "holding"

---

## Testing

28 tests covering:

1. R arithmetic (BUY, SELL, missing stop)
2. SELL calculations
3. Commission/swap effects
4. Premises calculation
5. Partial close aggregation
6. Bootstrap intervals (seeded, percentiles)
7. Permutation p-values
8. BH correction
9. Backtest filtering
10. Notion sync (no duplicates)
11. MT5 aggregation
12. Timezone/killzone classification
13. Calendar (day/week/month boundaries)
14. Dashboard streak
15. Leap year handling
16. Empty month handling
17. Single-trade month handling
18. Weekday statistics
19. NaN handling
20. Re-import (update, preserve journal)
21. UI API responses
22. Secrets handling
23. MT5 optional
24. Demo planted effects
25. Config loading
26. Error handling (loud, not silent)
27. Liq swept tracking
28. NOT DEFINED verdicts

---

## Windows Release

**GitHub Actions:**

1. test (Linux) – 28 tests + demo
2. build (Windows) – tests again, PyInstaller, smoke test
3. release (on tag) – GitHub Release with exe/installer

---

**Specification Version:** 1.0  
**Status:** Authoritative  
**Last Updated:** 2026-09-02