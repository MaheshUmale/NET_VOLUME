import logging
from python_engine.models.data_models import MarketEvent, MessageType, Sentiment
from python_engine.models.trade import TradeSide

logger = logging.getLogger(__name__)

class TrendOIStrategyHandler:
    """
    Simplified high-conviction Option Buying Strategy.
    Logic:
    1. Market Structure must be BULLISH (HH/HL) for Call or BEARISH (LH/LL) for Put.
    2. Sentiment (Volume PCR & RSI) must align.
    3. OI Change must confirm (Put writing at Support for Bullish).
    """
    def __init__(self, order_orchestrator):
        self.order_orchestrator = order_orchestrator

    def on_event(self, event: MarketEvent):
        if event.type != MessageType.MARKET_UPDATE:
            return

        candle = event.candle
        sentiment = event.sentiment
        structure = getattr(event, 'market_structure', {})

        if not candle or not sentiment or not structure:
            return

        regime = sentiment.regime
        # We use the regime derived from Volume PCR & RSI in SentimentHandler

        # Bullish Entry Condition
        if regime == "COMPLETE_BULLISH" and structure.get('regime') == "BULLISH":
            # Extra check: Price above Support Wall
            if candle.close > sentiment.oi_wall_below:
                self._trigger_trade(event, "BUY", "CALL")

        # Bearish Entry Condition
        elif regime == "COMPLETE_BEARISH" and structure.get('regime') == "BEARISH":
            # Extra check: Price below Resistance Wall
            if candle.close < sentiment.oi_wall_above:
                self._trigger_trade(event, "BUY", "PUT")

    def _trigger_trade(self, event, side, option_type):
        # Prevent multiple entries for the same symbol/side in a short window
        # (Implementation omitted for brevity, but handled by OrderOrchestrator's open_positions check)

        # We simulate a "definition" object to satisfy OrderOrchestrator if needed,
        # or we update OrderOrchestrator to handle direct signals.

        # For now, I'll log it.
        logger.info(f"!!! SIGNAL !!! {side} {option_type} on {event.symbol} at {event.candle.close}")

        # In a real setup, we would call:
        # self.order_orchestrator.execute_simple_trade(event.symbol, side, option_type, event.candle)
