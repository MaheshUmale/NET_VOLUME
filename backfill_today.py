import argparse
import logging
from datetime import datetime
from data_sourcing.ingestion import IngestionManager
from python_engine.utils.symbol_master import MASTER as SymbolMaster
from python_engine.engine_config import Config

# Standardized Logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Backfill today's data from start of day.")
    parser.add_argument('--symbol', type=str, default="NIFTY", help="Symbol to backfill (NIFTY/BANKNIFTY)")
    parser.add_argument('--full-options', action='store_true', help="Fetch granular options data")

    args = parser.parse_args()

    # Initialize components
    Config.load('config.json')
    SymbolMaster.initialize()
    manager = IngestionManager()

    today_str = datetime.now().strftime('%Y-%m-%d')
    logger.info(f"Starting backfill for {args.symbol} on {today_str}...")

    try:
        # Resolve symbols
        symbols_to_process = []
        if args.symbol.upper() == "NIFTY":
            symbols_to_process = ["NSE_INDEX|Nifty 50"]
        elif args.symbol.upper() == "BANKNIFTY":
            symbols_to_process = ["NSE_INDEX|Nifty Bank"]
        else:
            symbols_to_process = [args.symbol]

        for sym in symbols_to_process:
            logger.info(f"Processing {sym}...")
            manager.ingest_historical_data(
                symbol=sym,
                from_date=today_str,
                to_date=today_str,
                full_options=args.full_options,
                force=True
            )

        logger.info("Backfill completed successfully.")
    except Exception as e:
        logger.error(f"Backfill failed: {e}")

if __name__ == "__main__":
    main()
