from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.engine import BacktestEngineConfig
from nautilus_trader.core.datetime import dt_to_unix_nanos
from nautilus_trader.model.currencies import AUD
from nautilus_trader.model.enums import AccountType, BookType
from nautilus_trader.model.enums import OMSType
from nautilus_trader.model.instruments.betting import BettingInstrument
from nautilus_trader.model.objects import Money
import pandas as pd
import fsspec
from nautilus_trader.adapters.betfair.common import BETFAIR_VENUE
from nautilus_trader.adapters.betfair.providers import BetfairInstrumentProvider
from nautilus_trader.adapters.betfair.util import make_betfair_reader
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.backtest.data.providers import TestDataProvider

from adapter import CricInfoEnvelope, make_generic_data
from strategy_cric import PairTrader, PairTraderConfig


def read_cric_info_file():
    data = pd.read_pickle("/Users/julianbennettlongley/one_msg.pkl")
    return [make_generic_data(CricInfoEnvelope(d, ts_init=dt_to_unix_nanos(pd.Timestamp(d.recentBallCommentary.ballComments[0].timestamp)))) for d in [data]]


if __name__ == "__main__":
    # Configure backtest engine
    config = BacktestEngineConfig(
        trader_id="BACKTESTER-001",
        exec_engine={"allow_cash_positions": True},  # Retain original behaviour for now
    )
    # Build the backtest engine
    engine = BacktestEngine(config=config)

    # Load data
    with fsspec.open("/Users/julianbennettlongley/Desktop/1.191550075.bz2", "rb", compression='infer') as f:
        raw_data = f.read()
    instrument_provider = BetfairInstrumentProvider.from_instruments([])
    reader = make_betfair_reader(instrument_provider=instrument_provider)
    data = list(reader.parse(raw_data))

    # Add instruments and market data to engine
    instruments = [d for d in data if isinstance(d, BettingInstrument)]
    data = [d for d in data if not isinstance(d, BettingInstrument)]

    for instrument in instruments:
        engine.add_instrument(instrument)
    engine.add_data(data)

    # Add cricinfo data to engine
    cric_infos = read_cric_info_file()
    engine.add_data(cric_infos, client_id=ClientId('cricinfo'))

    # Add an exchange (multiple exchanges possible)
    # Add starting balances for single-currency or multi-currency accounts
    engine.add_venue(
        venue=BETFAIR_VENUE,
        oms_type=OMSType.NETTING,
        account_type=AccountType.CASH,  # Spot cash account
        base_currency=None,  # Multi-currency account
        starting_balances=[Money(1_000_000, AUD)],
        book_type=BookType.L2_MBP
    )

    # Configure your strategy
    config = PairTraderConfig(
        instrument_id=str(instrument.id),
    )
    # Instantiate and add your strategy
    strategy = PairTrader(config=config)
    engine.add_strategy(strategy=strategy)

    # Run the engine (from start to end of data)
    engine.run()

    # For repeated backtest runs make sure to reset the engine
    engine.reset()

    # Good practice to dispose of the object
    engine.dispose()