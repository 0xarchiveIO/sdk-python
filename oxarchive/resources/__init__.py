"""Resource modules."""

from .orderbook import OrderBookResource
from .trades import TradesResource
from .candles import CandlesResource
from .instruments import InstrumentsResource
from .funding import FundingResource
from .openinterest import OpenInterestResource

__all__ = [
    "OrderBookResource",
    "TradesResource",
    "CandlesResource",
    "InstrumentsResource",
    "FundingResource",
    "OpenInterestResource",
]
