"""Type definitions for the 0xarchive SDK."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


# =============================================================================
# Base Types
# =============================================================================


class ApiResponse(BaseModel):
    """Standard API response wrapper."""

    success: bool
    count: int
    request_id: str


# =============================================================================
# Order Book Types
# =============================================================================


class OrderBook(BaseModel):
    """Order book snapshot."""

    coin: str
    timestamp: int
    bids: list[tuple[str, str]]
    asks: list[tuple[str, str]]
    mid_price: str
    spread: str
    spread_bps: str


# =============================================================================
# Trade Types
# =============================================================================


class Trade(BaseModel):
    """Trade/fill record."""

    id: str
    coin: str
    side: Literal["buy", "sell"]
    price: str
    size: str
    value: str
    timestamp: int
    trade_type: str


# =============================================================================
# Candle Types
# =============================================================================

CandleInterval = Literal["1m", "5m", "15m", "1h", "4h", "1d"]


class Candle(BaseModel):
    """OHLCV candle."""

    coin: str
    interval: str
    timestamp: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    trades: int


# =============================================================================
# Instrument Types
# =============================================================================


class Instrument(BaseModel):
    """Trading instrument metadata."""

    coin: str
    name: str
    sz_decimals: int
    max_leverage: int
    only_isolated: bool
    is_active: bool


# =============================================================================
# Funding Types
# =============================================================================


class FundingRate(BaseModel):
    """Funding rate record."""

    coin: str
    funding_rate: str
    premium: str
    timestamp: int


# =============================================================================
# Open Interest Types
# =============================================================================


class OpenInterest(BaseModel):
    """Open interest record."""

    coin: str
    open_interest: str
    timestamp: int


# =============================================================================
# WebSocket Types
# =============================================================================

WsChannel = Literal["orderbook", "trades", "ticker", "all_tickers", "candles", "funding", "openinterest"]
WsConnectionState = Literal["connecting", "connected", "disconnected", "reconnecting"]


class WsSubscribed(BaseModel):
    """Subscription confirmed from server."""

    type: Literal["subscribed"]
    channel: WsChannel
    coin: Optional[str] = None


class WsUnsubscribed(BaseModel):
    """Unsubscription confirmed from server."""

    type: Literal["unsubscribed"]
    channel: WsChannel
    coin: Optional[str] = None


class WsPong(BaseModel):
    """Pong response from server."""

    type: Literal["pong"]


class WsError(BaseModel):
    """Error from server."""

    type: Literal["error"]
    message: str


class WsData(BaseModel):
    """Data message from server."""

    type: Literal["data"]
    channel: WsChannel
    coin: str
    data: dict


# =============================================================================
# WebSocket Replay Types (Option B - Like Tardis.dev)
# =============================================================================


class WsReplayStarted(BaseModel):
    """Replay started response."""

    type: Literal["replay_started"]
    channel: WsChannel
    coin: str
    start: int
    end: int
    speed: float
    total_records: int


class WsReplayPaused(BaseModel):
    """Replay paused response."""

    type: Literal["replay_paused"]
    current_timestamp: int


class WsReplayResumed(BaseModel):
    """Replay resumed response."""

    type: Literal["replay_resumed"]
    current_timestamp: int


class WsReplayCompleted(BaseModel):
    """Replay completed response."""

    type: Literal["replay_completed"]
    channel: WsChannel
    coin: str
    records_sent: int


class WsReplayStopped(BaseModel):
    """Replay stopped response."""

    type: Literal["replay_stopped"]


class WsHistoricalData(BaseModel):
    """Historical data point (replay mode)."""

    type: Literal["historical_data"]
    channel: WsChannel
    coin: str
    timestamp: int
    data: dict


# =============================================================================
# WebSocket Bulk Stream Types (Option D - Like Databento)
# =============================================================================


class WsStreamStarted(BaseModel):
    """Stream started response."""

    type: Literal["stream_started"]
    channel: WsChannel
    coin: str
    start: int
    end: int
    batch_size: int
    total_records: int


class WsStreamProgress(BaseModel):
    """Stream progress response."""

    type: Literal["stream_progress"]
    records_sent: int
    total_records: int
    progress_pct: float


class TimestampedRecord(BaseModel):
    """A record with timestamp."""

    timestamp: int
    data: dict


class WsHistoricalBatch(BaseModel):
    """Stream batch (bulk data)."""

    type: Literal["historical_batch"]
    channel: WsChannel
    coin: str
    batch_index: int
    records: list[TimestampedRecord]


class WsStreamCompleted(BaseModel):
    """Stream completed response."""

    type: Literal["stream_completed"]
    channel: WsChannel
    coin: str
    records_sent: int


class WsStreamStopped(BaseModel):
    """Stream stopped response."""

    type: Literal["stream_stopped"]


# =============================================================================
# Error Types
# =============================================================================


class OxArchiveError(Exception):
    """SDK error class."""

    def __init__(self, message: str, code: int, request_id: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.request_id = request_id

    def __str__(self) -> str:
        if self.request_id:
            return f"[{self.code}] {self.message} (request_id: {self.request_id})"
        return f"[{self.code}] {self.message}"


# Type alias for timestamp parameters
Timestamp = Union[int, str, datetime]
