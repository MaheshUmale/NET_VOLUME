import asyncio
import pandas as pd
import logging
from datetime import datetime
from python_engine.models.data_models import MarketEvent, MessageType, VolumeBar
from python_engine.engine_config import Config
from python_engine.core.order_orchestrator import OrderOrchestrator
from python_engine.core.trade_logger import TradeLog
from python_engine.core.trading_engine import TradingEngine
from data_sourcing.data_manager import DataManager
from python_engine.utils.symbol_master import MASTER as SymbolMaster

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] - %(message)s')
logger = logging.getLogger(__name__)

class PollingLiveEngine:
    def __init__(self):
        Config.load('config.json')
        self.access_token = Config.get('upstox_access_token')
        self.data_manager = DataManager(access_token=self.access_token)
        self.trade_log = TradeLog('live_trades.csv')
        self.order_orchestrator = OrderOrchestrator(self.trade_log, self.data_manager, "live")
        self.engine = TradingEngine(self.order_orchestrator, self.data_manager, Config.get('strategies_dir'))
        self.symbols = ["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank"]
        self._last_processed_ts = {}
        self._vol_history = {} # {ticker: [net_vol, ...]}

    async def poll_once(self):
        for symbol in self.symbols:
            try:
                ticker = SymbolMaster.get_canonical_ticker(symbol)
                key = SymbolMaster.get_upstox_key(symbol)

                resp = self.data_manager.upstox_client.get_intra_day_candle_data(key, '1m')
                if resp and hasattr(resp, 'data') and len(resp.data.candles) >= 2:
                    c = resp.data.candles[1] # Latest completed candle
                    ts_str = c[0]

                    if ticker not in self._last_processed_ts or ts_str != self._last_processed_ts[ticker]:
                        self._last_processed_ts[ticker] = ts_str
                        ts_dt = pd.to_datetime(ts_str)

                        logger.info(f"New completed candle for {ticker} at {ts_str}")

                        # Store in DB
                        df = pd.DataFrame([{
                            'timestamp': ts_dt,
                            'open': float(c[1]), 'high': float(c[2]), 'low': float(c[3]), 'close': float(c[4]),
                            'volume': int(c[5])
                        }])
                        self.data_manager.db_manager.store_historical_candles(ticker, 'NSE', '1m', df)

                        # Fetch Sentiment
                        # Fetch chain for volume calculation
                        full_symbol = "NSE_INDEX|Nifty 50" if "NIFTY" in ticker else "NSE_INDEX|Nifty Bank"
                        chain = self.data_manager.get_option_chain(full_symbol, mode='live')
                        df_chain = pd.DataFrame(chain) if chain else pd.DataFrame()

                        # Calculate Net Vol RSI in-memory
                        total_call_vol = df_chain['call_volume'].sum() if 'call_volume' in df_chain.columns else 0
                        total_put_vol = df_chain['put_volume'].sum() if 'put_volume' in df_chain.columns else 0
                        net_vol = total_call_vol - total_put_vol

                        if ticker not in self._vol_history: self._vol_history[ticker] = []
                        self._vol_history[ticker].append(net_vol)
                        if len(self._vol_history[ticker]) > 14: self._vol_history[ticker].pop(0)

                        net_vol_rsi = 50.0
                        if len(self._vol_history[ticker]) >= 2:
                            series = pd.Series(self._vol_history[ticker])
                            delta = series.diff().dropna()
                            if not delta.empty:
                                gain = (delta.where(delta > 0, 0)).mean()
                                loss = (-delta.where(delta < 0, 0)).mean()
                                rs = gain / (loss if loss > 0 else 0.001)
                                net_vol_rsi = 100 - (100 / (1 + rs))

                        sentiment = self.data_manager.get_current_sentiment(ticker, timestamp=ts_dt.timestamp(), mode='live')
                        sentiment.net_vol_rsi = float(net_vol_rsi)

                        event = MarketEvent(
                            type=MessageType.MARKET_UPDATE,
                            timestamp=int(ts_dt.timestamp()),
                            symbol=ticker,
                            candle=VolumeBar(
                                symbol=ticker, timestamp=int(ts_dt.timestamp()),
                                open=float(c[1]), high=float(c[2]), low=float(c[3]), close=float(c[4]),
                                volume=int(c[5])
                            ),
                            sentiment=sentiment
                        )

                        logger.info(f"Processing {ticker} | Price: {c[4]} | PCR: {sentiment.pcr} | Vol PCR: {sentiment.volume_pcr} | RSI: {sentiment.net_vol_rsi:.2f}")
                        for handler in self.engine.pipeline:
                            handler.on_event(event)
            except Exception as e:
                logger.error(f"Error polling {symbol}: {e}")

    async def start(self):
        logger.info("Starting Polling-based Live Engine (30-minute test)")
        end_time = time.time() + 1800 # 30 minutes
        while time.time() < end_time:
            await self.poll_once()
            await asyncio.sleep(10) # Poll every 10 seconds

import time
if __name__ == "__main__":
    engine = PollingLiveEngine()
    asyncio.run(engine.start())
