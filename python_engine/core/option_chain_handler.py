from typing import Dict, List
from python_engine.models.data_models import MarketEvent, OptionChainData, MessageType

class OptionChainHandler:
    def __init__(self):
        self._latest_option_chain: Dict[int, OptionChainData] = {}

    def on_event(self, event: MarketEvent):
        if event.type in (MessageType.OPTION_CHAIN_UPDATE, MessageType.MARKET_UPDATE):
            if event.option_chain:
                for data in event.option_chain:
                    strike = getattr(data, 'strike', data.get('strike')) if not isinstance(data, dict) else data.get('strike')
                    if strike is not None:
                        # Ensure it's an OptionChainData object
                        if isinstance(data, dict):
                            from python_engine.utils.dataclass_factory import from_dict
                            obj = from_dict(OptionChainData, data)
                            self._latest_option_chain[strike] = obj
                        else:
                            self._latest_option_chain[strike] = data

    def get_latest_option_chain(self) -> Dict[int, OptionChainData]:
        return self._latest_option_chain
