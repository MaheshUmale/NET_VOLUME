import asyncio
import threading
import time
import pandas as pd
import logging
from datetime import datetime
import upstox_client
from python_engine.models.data_models import MarketEvent, MessageType, VolumeBar
from python_engine.engine_config import Config
from python_engine.core.order_orchestrator import OrderOrchestrator
from python_engine.core.trade_logger import TradeLog
from python_engine.core.trading_engine import TradingEngine
from data_sourcing.data_manager import DataManager
from python_engine.utils.symbol_master import MASTER as SymbolMaster

# Standardized Logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] - %(message)s')
logger = logging.getLogger(__name__)

class LiveTradingEngine:
    def __init__(self, loop):
        self.loop = loop
        Config.load('config.json')
        self.access_token = Config.get('upstox_access_token')
        self.data_manager = DataManager(access_token=self.access_token)
        self.trade_log = TradeLog('live_trades.csv')
        self.order_orchestrator = OrderOrchestrator(self.trade_log, self.data_manager, "live")
        self.engine = TradingEngine(self.order_orchestrator, self.data_manager, Config.get('strategies_dir'))
        self.symbols = ["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank"]
        self.subscribed_instruments = ["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank"]
        self._last_min = {}

    def _get_subscriptions(self):
        subs = set(self.symbols)
        try:
            spots = {"NIFTY": self.data_manager.get_last_traded_price("NSE_INDEX|Nifty 50", mode='live'),
                     "BANKNIFTY": self.data_manager.get_last_traded_price("NSE_INDEX|Nifty Bank", mode='live')}
            fno = self.data_manager.instrument_loader.get_upstox_instruments(["NIFTY", "BANKNIFTY"], spots)
            for data in fno.values():
                for opt in data.get('options', []):
                    if opt.get('ce'): subs.add(opt['ce'])
                    if opt.get('pe'): subs.add(opt['pe'])
        except Exception as e:
            logger.warning(f"Error resolving F&O subscriptions: {e}")

        valid_subs = []
        for s in subs:
            key = SymbolMaster.get_upstox_key(s) if "|" not in s else s
            if key: valid_subs.append(key)
        return list(set(valid_subs))

    def on_message(self, message):
        feeds = getattr(message, 'feeds', {})
        if not feeds: return

        for key, feed in feeds.items():
            logger.info(f'Message from {key}')
            full_feed = getattr(feed, 'full_feed', None)
            if not full_feed: continue

            market_ohlc = getattr(full_feed, 'market_ohlc', None)
            if not market_ohlc: continue

            ohlc_list = getattr(market_ohlc, 'ohlc', [])
            candle_1m = next((o for o in ohlc_list if getattr(o, 'interval', '') == 'I1'), None)
            if not candle_1m: continue

            ts = int(candle_1m.ts)
            ticker = SymbolMaster.get_ticker_from_key(key)
            if ticker not in self._last_min:
                self._last_min[ticker] = ts
                continue

            if ts > self._last_min[ticker]:
                self._last_min[ticker] = ts
                logger.info(f"New 1m candle for {ticker} at {ts}")
                self.loop.call_soon_threadsafe(lambda k=key, t=ticker: asyncio.create_task(self.process_candle(k, t)))

    async def process_candle(self, key, ticker):
        try:
            resp = self.data_manager.upstox_client.get_intra_day_candle_data(key, '1m')
            if resp and hasattr(resp, 'data') and len(resp.data.candles) >= 2:
                c = resp.data.candles[1]
                ts_dt = pd.to_datetime(c[0])
                df = pd.DataFrame([{
                    'timestamp': ts_dt,
                    'open': float(c[1]), 'high': float(c[2]), 'low': float(c[3]), 'close': float(c[4]),
                    'volume': int(c[5])
                }])
                self.data_manager.db_manager.store_historical_candles(ticker, 'NSE', '1m', df)

                sentiment = self.data_manager.get_current_sentiment(ticker, timestamp=ts_dt.timestamp(), mode='live')

                event = MarketEvent(
                    type=MessageType.MARKET_UPDATE,
                    timestamp=int(ts_dt.timestamp()),
                    symbol=ticker,
                    candle=VolumeBar(
                        symbol=ticker,
                        timestamp=int(ts_dt.timestamp()),
                        open=float(c[1]), high=float(c[2]), low=float(c[3]), close=float(c[4]),
                        volume=int(c[5])
                    ),
                    sentiment=sentiment
                )
                logger.info(f"Processing Event for {ticker} | Price: {c[4]} | PCR: {sentiment.pcr} | Vol PCR: {sentiment.volume_pcr}")
                for handler in self.engine.pipeline:
                    handler.on_event(event)
        except Exception as e:
            logger.error(f"Error processing candle for {ticker}: {e}")

    def start_websocket(self):
        conf = upstox_client.Configuration()
        conf.access_token = self.access_token
        api_client = upstox_client.ApiClient(conf)

        streamer = upstox_client.MarketDataStreamerV3(api_client, self.subscribed_instruments, "ltpc")
        streamer.on("message", self.on_message)
        streamer.on("error", lambda error: logger.error(f"Websocket Error: {error}"))
        streamer.on("open", lambda: logger.info("Websocket Connection Opened"))

        threading.Thread(target=streamer.connect, daemon=True).start()

    async def start(self):
        logger.info(f"Starting Live Engine for {len(self.subscribed_instruments)} instruments")
        self.start_websocket()
        while True:
            await asyncio.sleep(1)

async def run_live():
    engine = LiveTradingEngine(asyncio.get_running_loop())
    await engine.start()
