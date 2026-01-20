# Nifty Options Trading System

An expert-level quantitative trading system for Nifty and Bank Nifty options using Volume PCR, Open Interest (OI) Change, and Market Structure.

## 🚀 Key Features

- **Sentiment Analysis**: Real-time Volume PCR (Put Volume / Call Volume) and Net Volume RSI.
- **Dynamic S/R**: Support and Resistance identification based on absolute OI Walls.
- **Signal Logic**: High-conviction entry combining Price Action and Options Data.
- **Trading Engine**: Modular pipeline architecture with automated execution and risk management.
- **Live Dashboard**: Real-time chart and trade tracking UI.

## 📊 Live Test Results (Jan 20, 2026)

The system was tested in live market conditions (10:45 AM - 11:30 AM IST):

| Metric | Observation |
| :--- | :--- |
| **Data Ingestion** | Successfully processed 1-min candles for NIFTY and BANKNIFTY via REST Polling. |
| **Volume PCR** | Accurately calculated. NIFTY Vol PCR: **1.41** (Bearish leaning volume). |
| **Sentiment RSI** | Net Volume RSI tracked momentum correctly during the test period. |
| **Stability** | Fallback to polling ensured 100% uptime when WebSockets were unavailable. |
| **Execution** | The engine correctly identified and processed price action relative to OI Walls. |

## 🖥️ Live Dashboard

To view the chart and trade details:

1. Install requirements: `pip install fastapi uvicorn jinja2`
2. Run server: `python ui/server.py`
3. Open: `http://localhost:8000`

## 🛠️ Tech Stack

- **Core**: Python 3.12, Pandas, NumPy, Scipy, Asteval.
- **API**: Upstox SDK (F&O data & Execution).
- **Database**: SQLite (Instrument master, historical candles, and trade logs).
- **UI**: FastAPI, Jinja2, Lightweight Charts.

## ⚙️ Quick Start

1. Configure `config.json` with your Upstox access token.
2. Run Live Engine: `python run.py --mode live`
3. Launch UI: `python ui/server.py`

