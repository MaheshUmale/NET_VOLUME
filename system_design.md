# Nifty Options Trading System Design

This document specifies the technical architecture and logic for an automated Nifty options trading system based on Volume PCR, OI Change, and Price Action.

## 1. Architectural Diagram Description

The system follows a modular, event-driven architecture designed for low-latency processing and robust risk management.

### A. Data Ingestion Module (The Gateway)
- **Real-time Connector**: Utilizes WebSocket/REST APIs (e.g., Upstox, Angel One) to stream Nifty 50 Spot prices and the complete Option Chain.
- **Data Normalizer**: Standardizes raw JSON payloads into structured internal formats (DataModels).
- **Persistence Layer**: (Optional) Stores ticks/candles in a local SQLite or Time-series database for backtesting and audit.

### B. Analytics Engine (The Brain)
- **Sentiment Module**:
    - Calculates **Volume PCR** (Put Volume / Call Volume).
    - Computes **Net Volume RSI** using $(\Sigma \text{Call Vol} - \Sigma \text{Put Vol})$ over a 5-minute rolling window.
- **Market Structure Handler**:
    - Identifies **Pivots** (Swing Highs/Lows) for price-action based S/R.
    - Identifies **OI Walls**: Strikes with the highest absolute Call OI (Resistance) and Put OI (Support).
- **OI Change Tracker**: Monitors $\Delta OI$ every 5 minutes to identify institutional "Writing" or "Unwinding".

### C. Trigger Engine (The Decision Maker)
- Evaluates signals based on the convergence of Price, Volume, and OI.
- **Bullish/Bearish Signal Logic**: Cross-references Spot price relative to OI Walls with Volume PCR trends.

### D. Risk Management Unit (The Shield)
- **Position Sizer**: Calculates quantity based on 1% capital risk.
- **Dynamic SL/TP**: Set SL based on Spot levels (e.g., below the Support OI Wall) rather than just premium.
- **Volatility Filter**: Adjusts exposure or halts trading during extreme India VIX spikes (>25).

### E. Execution Engine (The Actor)
- **Order Orchestrator**: Handles entry, exit, and trailing SL orders.
- **Slippage Monitor**: Ensures trades are only executed in highly liquid ATM/OTM strikes.

---

## 2. Data Structure Definitions

### A. Net Volume & Sentiment (`NetVolStats`)
| Field | Type | Description |
| :--- | :--- | :--- |
| `timestamp` | Datetime | 5-minute interval timestamp |
| `total_call_vol` | Int | Sum of volume across all active Call strikes |
| `total_put_vol` | Int | Sum of volume across all active Put strikes |
| `net_vol_diff` | Int | `total_call_vol - total_put_vol` |
| `net_vol_rsi` | Float | RSI (0-100) calculated on `net_vol_diff` |
| `volume_pcr` | Float | `total_put_vol / total_call_vol` |

### B. OI Changes (`OIChangeMap`)
| Field | Type | Description |
| :--- | :--- | :--- |
| `strike` | Int | Option strike price |
| `call_delta_oi` | Int | Change in Call OI over the window |
| `put_delta_oi` | Int | Change in Put OI over the window |
| `call_status` | Enum | `Addition`, `Unwinding`, or `Neutral` |
| `put_status` | Enum | `Addition`, `Unwinding`, or `Neutral` |
| `oi_wall_type` | Enum | `Support` (Max Put OI) or `Resistance` (Max Call OI) |

---

## 3. Signal Generation Algorithm (Pseudo-code)

```python
def check_signals(market_event):
    # 1. Extract Analytics
    spot = market_event.spot_price
    pcr = market_event.sentiment.volume_pcr
    net_vol_rsi = market_event.sentiment.net_vol_rsi

    res_wall = market_event.market_structure.oi_wall_above  # Max Call OI
    sup_wall = market_event.market_structure.oi_wall_below  # Max Put OI

    # Identify Top 3 OI Additions
    call_additions = get_top_n_oi_change(type='Call', n=3, order='desc')
    put_additions = get_top_n_oi_change(type='Put', n=3, order='desc')

    # 2. Bullish Logic
    is_price_bullish = spot > res_wall  # Breakout above Call Resistance
    is_volume_bullish = (net_vol_rsi > 60) and (pcr < 0.7) # High Call Vol + Contrarian PCR
    is_oi_bullish = (put_additions[0].strike >= spot - 100) # Aggressive Put Writing at Support

    if is_price_bullish and is_volume_bullish and is_oi_bullish:
        return Signal(type='BUY_CALL', strategy='Bull_Call_Spread', strike='ATM')

    # 3. Bearish Logic
    is_price_bearish = spot < sup_wall  # Breakdown below Put Support
    is_volume_bearish = (net_vol_rsi < 40) and (pcr > 1.3) # High Put Vol + Contrarian PCR
    is_oi_bearish = (call_additions[0].strike <= spot + 100) # Aggressive Call Writing at Resistance

    if is_price_bearish and is_volume_bearish and is_oi_bearish:
        return Signal(type='BUY_PUT', strategy='Bear_Put_Spread', strike='ATM')

    # 4. Reversal Logic
    if spot >= res_wall and is_significant_unwinding(res_wall, 'Call'):
        return Signal(type='REVERSAL_BULLISH', reason='Short Covering')

    return None
```

---

## 4. Example Trade Rationale: Bullish Breakout

**Scenario**: Nifty is trading at 21,520. The 21,500 strike has the highest Call OI (Resistance Wall).

- **Price Action**: Nifty spot breaks 21,535 with a strong 5-minute green candle.
- **Volume Sentiment**:
    - `Net Volume RSI` jumps from 45 to 68.
    - `Volume PCR` is 0.65, indicating heavy call buying relative to puts.
- **OI Analysis**:
    - 21,500 Call OI shows a decrease of 1.2M shares (Short Unwinding/Covering).
    - 21,400 and 21,500 Put OI increases by 2.5M shares (Heavy Put Writing/Support Building).
- **VIX**: India VIX is stable at 14.5 (No immediate IV crush risk).

**AI Recommendation**:
- **Strategy**: Buy NIFTY 21500 Call (Weekly Expiry).
- **Entry**: 21,535 (Spot).
- **Stop-Loss**: 21,490 (Below the converted support wall).
- **Target**: 21,650 (Next psychological resistance).
- **Reasoning**: Bullish breakout confirmed by Call unwinding at 21,500 and aggressive Put writing. Net Volume RSI supports momentum.

---

## 5. Integrated Implementation Details

The system is integrated into the `sosnew` engine architecture.

### A. Data Enrichment (`data_sourcing/ingestion.py`)
The `IngestionManager` now calculates Volume PCR and Net Volume RSI during the stats enrichment phase.
```python
def compute_rsi(series, window=5):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)

# Volume PCR & RSI Calculation
vol_pcr = total_put_vol / total_call_vol
net_vol_rsi = compute_rsi(net_volume_series)
```

### B. Sentiment Intelligence (`python_engine/core/sentiment_handler.py`)
The `SentimentHandler` prioritizes Volume-based metrics to define the market regime:
- **COMPLETE_BULLISH**: `net_vol_rsi > 60` AND `volume_pcr < 0.8`
- **COMPLETE_BEARISH**: `net_vol_rsi < 40` AND `volume_pcr > 1.2`

### C. Automated Strategy (`strategies/nifty_vol_oi_momentum.json`)
The strategy is defined as a multi-phase state machine:
1. **Setup Phase**: Monitors for Volume PCR and RSI alignment.
2. **Trigger Phase**: Executes when Price breaks above the `oi_wall_above` (Call Resistance).

### How to Run:
1. **Ingest Data**: `python run.py --mode ingest --symbol NIFTY --from-date 2025-02-20 --to-date 2025-02-21`
2. **Backtest**: `python run.py --mode backtest --symbol NIFTY --from-date 2025-02-20 --to-date 2025-02-21`

---

## 6. Constraints & Risk Management
1. **Max Risk**: 1% of trading capital per trade.
2. **Liquidity**: Filter for contracts with `OI > 500,000` and `Volume > 100,000`.
3. **Execution**: Use **Limit Orders** to avoid slippage in fast-moving markets.
4. **Time Filter**: Avoid entries in the first 15 mins (9:15-9:30) and last 30 mins (15:00-15:30) of the market.
