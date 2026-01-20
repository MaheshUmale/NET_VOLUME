from python_engine.models.data_models import MarketEvent, Sentiment, MessageType

class SentimentHandler:
    PCR_EXTREME_BULLISH = 0.7
    PCR_EXTREME_BEARISH = 1.3
    PCR_NEUTRAL = 1.0

    def __init__(self):
        self._current_regime = "SIDEWAYS"

    def on_event(self, event: MarketEvent):
        if event.type in (MessageType.MARKET_UPDATE, MessageType.SENTIMENT_UPDATE):
            sentiment = event.sentiment
            if sentiment:
                regime = sentiment.regime
                if regime is None:
                    regime = self._determine_regime(sentiment)
                    sentiment.regime = regime
                self._current_regime = regime

    def get_regime(self) -> str:
        return self._current_regime

    def _determine_regime(self, sentiment: Sentiment) -> str:
        # 1. Volume & Net Vol RSI Based Sentiment (High Priority for Momentum)
        vol_rsi = sentiment.net_vol_rsi
        vol_pcr = sentiment.volume_pcr

        # Bullish: High Net Vol RSI (>60) and Low Volume PCR (<0.8 - contrarian)
        if vol_rsi > 60 and vol_pcr < 0.8:
            return "COMPLETE_BULLISH"

        # Bearish: Low Net Vol RSI (<40) and High Volume PCR (>1.2 - contrarian)
        if vol_rsi < 40 and vol_pcr > 1.2:
            return "COMPLETE_BEARISH"

        # 2. Use Smart Trend Logic if available (Secondary)
        if sentiment.smart_trend:
            if sentiment.smart_trend == "Long Buildup":
                return "BULLISH"
            elif sentiment.smart_trend == "Short Covering":
                return "BULLISH"
            elif sentiment.smart_trend == "Short Buildup":
                return "BEARISH"
            elif sentiment.smart_trend == "Long Unwinding":
                return "BEARISH"

        # 3. Fallback to OI PCR logic
        pcr = sentiment.pcr
        if pcr > 1.2:
            return "BULLISH"
        elif pcr < 0.6:
            return "BEARISH"

        return "SIDEWAYS"
