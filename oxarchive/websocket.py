"""
WebSocket client for 0xarchive real-time streaming, replay, and bulk download.

Examples:
    Real-time streaming:
        >>> ws = OxArchiveWs(WsOptions(api_key="ox_..."))
        >>> await ws.connect()
        >>> ws.on_orderbook(lambda coin, ob: print(f"{coin}: {ob.mid_price}"))
        >>> ws.subscribe_orderbook("BTC")

    Historical replay (like Tardis.dev):
        >>> ws = OxArchiveWs(WsOptions(api_key="ox_..."))
        >>> await ws.connect()
        >>> ws.on_historical_data(lambda coin, ts, data: print(f"{ts}: {data}"))
        >>> await ws.replay("orderbook", "BTC", start=time.time()*1000 - 86400000, speed=10)

    Bulk streaming (like Databento):
        >>> ws = OxArchiveWs(WsOptions(api_key="ox_..."))
        >>> await ws.connect()
        >>> batches = []
        >>> ws.on_batch(lambda coin, records: batches.extend(records))
        >>> await ws.stream("orderbook", "ETH", start=..., end=..., batch_size=1000)
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Set, Union

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
except ImportError:
    raise ImportError(
        "WebSocket support requires the 'websockets' package. "
        "Install with: pip install oxarchive[websocket]"
    )

from .types import (
    OrderBook,
    Trade,
    WsChannel,
    WsConnectionState,
    WsData,
    WsError,
    WsPong,
    WsSubscribed,
    WsUnsubscribed,
    WsReplayStarted,
    WsReplayPaused,
    WsReplayResumed,
    WsReplayCompleted,
    WsReplayStopped,
    WsHistoricalData,
    WsStreamStarted,
    WsStreamProgress,
    WsHistoricalBatch,
    WsStreamCompleted,
    WsStreamStopped,
    TimestampedRecord,
)

logger = logging.getLogger("oxarchive.websocket")

DEFAULT_WS_URL = "wss://api.0xarchive.io/ws"
DEFAULT_PING_INTERVAL = 30
DEFAULT_RECONNECT_DELAY = 1.0
DEFAULT_MAX_RECONNECT_ATTEMPTS = 10

# Server idle timeout is 60 seconds. The SDK sends pings every 30 seconds
# to keep the connection alive. The websockets library also automatically
# responds to WebSocket protocol-level ping frames from the server.


@dataclass
class WsOptions:
    """WebSocket connection options.

    The server sends WebSocket ping frames every 30 seconds and will disconnect
    idle connections after 60 seconds. This SDK automatically handles keep-alive
    by sending application-level pings at the configured interval.

    Attributes:
        api_key: Your 0xarchive API key
        ws_url: WebSocket server URL (default: wss://api.0xarchive.io/ws)
        auto_reconnect: Automatically reconnect on disconnect (default: True)
        reconnect_delay: Initial reconnect delay in seconds (default: 1.0)
        max_reconnect_attempts: Maximum reconnection attempts (default: 10)
        ping_interval: Interval between keep-alive pings in seconds (default: 30)
    """

    api_key: str
    ws_url: str = DEFAULT_WS_URL
    auto_reconnect: bool = True
    reconnect_delay: float = DEFAULT_RECONNECT_DELAY
    max_reconnect_attempts: int = DEFAULT_MAX_RECONNECT_ATTEMPTS
    ping_interval: float = DEFAULT_PING_INTERVAL


MessageHandler = Callable[[Union[WsSubscribed, WsUnsubscribed, WsPong, WsError, WsData]], None]
OrderbookHandler = Callable[[str, OrderBook], None]
TradesHandler = Callable[[str, list[Trade]], None]
StateHandler = Callable[[WsConnectionState], None]
ErrorHandler = Callable[[Exception], None]

# Replay handlers
HistoricalDataHandler = Callable[[str, int, dict], None]
ReplayStartHandler = Callable[[WsChannel, str, int, float], None]
ReplayCompleteHandler = Callable[[WsChannel, str, int], None]

# Stream handlers
BatchHandler = Callable[[str, list[TimestampedRecord]], None]
StreamStartHandler = Callable[[WsChannel, str, int], None]
StreamProgressHandler = Callable[[int, int, float], None]
StreamCompleteHandler = Callable[[WsChannel, str, int], None]


class OxArchiveWs:
    """WebSocket client for real-time data streaming."""

    def __init__(self, options: WsOptions):
        """Initialize the WebSocket client.

        Args:
            options: WebSocket connection options
        """
        self.options = options
        self._ws: Optional[WebSocketClientProtocol] = None
        self._state: WsConnectionState = "disconnected"
        self._subscriptions: Set[str] = set()
        self._reconnect_attempts = 0
        self._running = False
        self._ping_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None

        # Event handlers
        self._on_message: Optional[MessageHandler] = None
        self._on_orderbook: Optional[OrderbookHandler] = None
        self._on_trades: Optional[TradesHandler] = None
        self._on_state_change: Optional[StateHandler] = None
        self._on_error: Optional[ErrorHandler] = None
        self._on_open: Optional[Callable[[], None]] = None
        self._on_close: Optional[Callable[[int, str], None]] = None

        # Replay handlers (Option B)
        self._on_historical_data: Optional[HistoricalDataHandler] = None
        self._on_replay_start: Optional[ReplayStartHandler] = None
        self._on_replay_complete: Optional[ReplayCompleteHandler] = None

        # Stream handlers (Option D)
        self._on_batch: Optional[BatchHandler] = None
        self._on_stream_start: Optional[StreamStartHandler] = None
        self._on_stream_progress: Optional[StreamProgressHandler] = None
        self._on_stream_complete: Optional[StreamCompleteHandler] = None

    @property
    def state(self) -> WsConnectionState:
        """Get current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._ws is not None and self._ws.open

    async def connect(self) -> None:
        """Connect to the WebSocket server."""
        self._running = True
        await self._connect()

    async def _connect(self) -> None:
        """Internal connect method."""
        self._set_state("connecting")

        url = f"{self.options.ws_url}?apiKey={self.options.api_key}"

        try:
            self._ws = await websockets.connect(url)
            self._reconnect_attempts = 0
            self._set_state("connected")

            if self._on_open:
                self._on_open()

            # Resubscribe to all channels
            await self._resubscribe()

            # Start ping and receive tasks
            self._ping_task = asyncio.create_task(self._ping_loop())
            self._receive_task = asyncio.create_task(self._receive_loop())

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            if self._on_error:
                self._on_error(e)
            if self.options.auto_reconnect and self._running:
                await self._schedule_reconnect()
            else:
                self._set_state("disconnected")

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        self._running = False
        self._set_state("disconnected")

        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None

        if self._receive_task:
            self._receive_task.cancel()
            self._receive_task = None

        if self._ws:
            await self._ws.close(1000, "Client disconnect")
            self._ws = None

    def subscribe(self, channel: WsChannel, coin: Optional[str] = None) -> None:
        """Subscribe to a channel.

        Args:
            channel: Channel type
            coin: Coin symbol (required for coin-specific channels)
        """
        key = self._subscription_key(channel, coin)
        self._subscriptions.add(key)

        if self.is_connected:
            asyncio.create_task(self._send_subscribe(channel, coin))

    async def subscribe_async(self, channel: WsChannel, coin: Optional[str] = None) -> None:
        """Subscribe to a channel (async version)."""
        key = self._subscription_key(channel, coin)
        self._subscriptions.add(key)

        if self.is_connected:
            await self._send_subscribe(channel, coin)

    def subscribe_orderbook(self, coin: str) -> None:
        """Subscribe to order book updates for a coin."""
        self.subscribe("orderbook", coin)

    def subscribe_trades(self, coin: str) -> None:
        """Subscribe to trades for a coin."""
        self.subscribe("trades", coin)

    def subscribe_ticker(self, coin: str) -> None:
        """Subscribe to ticker updates for a coin."""
        self.subscribe("ticker", coin)

    def subscribe_all_tickers(self) -> None:
        """Subscribe to all tickers."""
        self.subscribe("all_tickers")

    def unsubscribe(self, channel: WsChannel, coin: Optional[str] = None) -> None:
        """Unsubscribe from a channel."""
        key = self._subscription_key(channel, coin)
        self._subscriptions.discard(key)

        if self.is_connected:
            asyncio.create_task(self._send_unsubscribe(channel, coin))

    async def unsubscribe_async(self, channel: WsChannel, coin: Optional[str] = None) -> None:
        """Unsubscribe from a channel (async version)."""
        key = self._subscription_key(channel, coin)
        self._subscriptions.discard(key)

        if self.is_connected:
            await self._send_unsubscribe(channel, coin)

    def unsubscribe_orderbook(self, coin: str) -> None:
        """Unsubscribe from order book updates for a coin."""
        self.unsubscribe("orderbook", coin)

    def unsubscribe_trades(self, coin: str) -> None:
        """Unsubscribe from trades for a coin."""
        self.unsubscribe("trades", coin)

    def unsubscribe_ticker(self, coin: str) -> None:
        """Unsubscribe from ticker updates for a coin."""
        self.unsubscribe("ticker", coin)

    def unsubscribe_all_tickers(self) -> None:
        """Unsubscribe from all tickers."""
        self.unsubscribe("all_tickers")

    # =========================================================================
    # Historical Replay (Option B) - Like Tardis.dev
    # =========================================================================

    async def replay(
        self,
        channel: WsChannel,
        coin: str,
        start: int,
        end: Optional[int] = None,
        speed: float = 1.0,
    ) -> None:
        """Start historical replay with timing preserved.

        Args:
            channel: Data channel to replay
            coin: Trading pair (e.g., 'BTC', 'ETH')
            start: Start timestamp (Unix ms)
            end: End timestamp (Unix ms, defaults to now)
            speed: Playback speed multiplier (1 = real-time, 10 = 10x faster)

        Example:
            >>> await ws.replay("orderbook", "BTC", start=time.time()*1000 - 86400000, speed=10)
        """
        msg = {
            "op": "replay",
            "channel": channel,
            "coin": coin,
            "start": start,
            "speed": speed,
        }
        if end is not None:
            msg["end"] = end
        await self._send(msg)

    async def replay_pause(self) -> None:
        """Pause the current replay."""
        await self._send({"op": "replay.pause"})

    async def replay_resume(self) -> None:
        """Resume a paused replay."""
        await self._send({"op": "replay.resume"})

    async def replay_seek(self, timestamp: int) -> None:
        """Seek to a specific timestamp in the replay.

        Args:
            timestamp: Unix timestamp in milliseconds
        """
        await self._send({"op": "replay.seek", "timestamp": timestamp})

    async def replay_stop(self) -> None:
        """Stop the current replay."""
        await self._send({"op": "replay.stop"})

    # =========================================================================
    # Bulk Streaming (Option D) - Like Databento
    # =========================================================================

    async def stream(
        self,
        channel: WsChannel,
        coin: str,
        start: int,
        end: int,
        batch_size: int = 1000,
    ) -> None:
        """Start bulk streaming for fast data download.

        Args:
            channel: Data channel to stream
            coin: Trading pair (e.g., 'BTC', 'ETH')
            start: Start timestamp (Unix ms)
            end: End timestamp (Unix ms)
            batch_size: Records per batch message

        Example:
            >>> await ws.stream("orderbook", "ETH", start=..., end=..., batch_size=1000)
        """
        await self._send({
            "op": "stream",
            "channel": channel,
            "coin": coin,
            "start": start,
            "end": end,
            "batch_size": batch_size,
        })

    async def stream_stop(self) -> None:
        """Stop the current bulk stream."""
        await self._send({"op": "stream.stop"})

    # Event handler setters

    def on_message(self, handler: MessageHandler) -> None:
        """Set handler for all messages."""
        self._on_message = handler

    def on_orderbook(self, handler: OrderbookHandler) -> None:
        """Set handler for orderbook data."""
        self._on_orderbook = handler

    def on_trades(self, handler: TradesHandler) -> None:
        """Set handler for trade data."""
        self._on_trades = handler

    def on_state_change(self, handler: StateHandler) -> None:
        """Set handler for state changes."""
        self._on_state_change = handler

    def on_error(self, handler: ErrorHandler) -> None:
        """Set handler for errors."""
        self._on_error = handler

    def on_open(self, handler: Callable[[], None]) -> None:
        """Set handler for connection open."""
        self._on_open = handler

    def on_close(self, handler: Callable[[int, str], None]) -> None:
        """Set handler for connection close."""
        self._on_close = handler

    # Replay event handlers (Option B)

    def on_historical_data(self, handler: HistoricalDataHandler) -> None:
        """Set handler for historical data points (replay mode).

        Handler receives: (coin, timestamp, data)
        """
        self._on_historical_data = handler

    def on_replay_start(self, handler: ReplayStartHandler) -> None:
        """Set handler for replay started event.

        Handler receives: (channel, coin, total_records, speed)
        """
        self._on_replay_start = handler

    def on_replay_complete(self, handler: ReplayCompleteHandler) -> None:
        """Set handler for replay completed event.

        Handler receives: (channel, coin, records_sent)
        """
        self._on_replay_complete = handler

    # Stream event handlers (Option D)

    def on_batch(self, handler: BatchHandler) -> None:
        """Set handler for batched data (bulk stream mode).

        Handler receives: (coin, records) where records is list of TimestampedRecord
        """
        self._on_batch = handler

    def on_stream_start(self, handler: StreamStartHandler) -> None:
        """Set handler for stream started event.

        Handler receives: (channel, coin, total_records)
        """
        self._on_stream_start = handler

    def on_stream_progress(self, handler: StreamProgressHandler) -> None:
        """Set handler for stream progress event.

        Handler receives: (records_sent, total_records, progress_pct)
        """
        self._on_stream_progress = handler

    def on_stream_complete(self, handler: StreamCompleteHandler) -> None:
        """Set handler for stream completed event.

        Handler receives: (channel, coin, records_sent)
        """
        self._on_stream_complete = handler

    # Private methods

    async def _send(self, msg: dict) -> None:
        """Send a message to the server."""
        if self._ws:
            await self._ws.send(json.dumps(msg))

    def _set_state(self, state: WsConnectionState) -> None:
        """Set state and notify handler."""
        self._state = state
        if self._on_state_change:
            self._on_state_change(state)

    def _subscription_key(self, channel: WsChannel, coin: Optional[str]) -> str:
        """Create subscription key."""
        return f"{channel}:{coin}" if coin else channel

    async def _send_subscribe(self, channel: WsChannel, coin: Optional[str]) -> None:
        """Send subscribe message."""
        if self._ws:
            msg = {"op": "subscribe", "channel": channel}
            if coin:
                msg["coin"] = coin
            await self._ws.send(json.dumps(msg))

    async def _send_unsubscribe(self, channel: WsChannel, coin: Optional[str]) -> None:
        """Send unsubscribe message."""
        if self._ws:
            msg = {"op": "unsubscribe", "channel": channel}
            if coin:
                msg["coin"] = coin
            await self._ws.send(json.dumps(msg))

    async def _resubscribe(self) -> None:
        """Resubscribe to all channels."""
        for key in self._subscriptions:
            parts = key.split(":", 1)
            channel = parts[0]
            coin = parts[1] if len(parts) > 1 else None
            await self._send_subscribe(channel, coin)  # type: ignore

    async def _ping_loop(self) -> None:
        """Send periodic pings."""
        try:
            while self._running and self.is_connected:
                await asyncio.sleep(self.options.ping_interval)
                if self._ws:
                    await self._ws.send(json.dumps({"op": "ping"}))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Ping error: {e}")

    async def _receive_loop(self) -> None:
        """Receive and process messages."""
        try:
            while self._running and self._ws:
                try:
                    message = await self._ws.recv()
                    self._handle_message(message)
                except websockets.ConnectionClosed as e:
                    logger.info(f"Connection closed: {e.code} {e.reason}")
                    if self._on_close:
                        self._on_close(e.code, e.reason)
                    if self.options.auto_reconnect and self._running:
                        await self._schedule_reconnect()
                    else:
                        self._set_state("disconnected")
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Receive error: {e}")
            if self._on_error:
                self._on_error(e)

    def _handle_message(self, raw: str) -> None:
        """Handle incoming message."""
        try:
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "subscribed":
                msg = WsSubscribed(**data)
                if self._on_message:
                    self._on_message(msg)

            elif msg_type == "unsubscribed":
                msg = WsUnsubscribed(**data)
                if self._on_message:
                    self._on_message(msg)

            elif msg_type == "pong":
                msg = WsPong(**data)
                if self._on_message:
                    self._on_message(msg)

            elif msg_type == "error":
                msg = WsError(**data)
                if self._on_message:
                    self._on_message(msg)

            elif msg_type == "data":
                msg = WsData(**data)
                if self._on_message:
                    self._on_message(msg)

                # Call typed handlers
                channel = data.get("channel")
                coin = data.get("coin", "")
                raw_data = data.get("data", {})

                if channel == "orderbook" and self._on_orderbook:
                    orderbook = OrderBook(**raw_data)
                    self._on_orderbook(coin, orderbook)

                elif channel == "trades" and self._on_trades:
                    trades = [Trade(**t) for t in raw_data]
                    self._on_trades(coin, trades)

            # Replay messages (Option B)
            elif msg_type == "replay_started" and self._on_replay_start:
                self._on_replay_start(
                    data["channel"], data["coin"], data["total_records"], data["speed"]
                )

            elif msg_type == "historical_data" and self._on_historical_data:
                self._on_historical_data(data["coin"], data["timestamp"], data["data"])

            elif msg_type == "replay_completed" and self._on_replay_complete:
                self._on_replay_complete(data["channel"], data["coin"], data["records_sent"])

            # Stream messages (Option D)
            elif msg_type == "stream_started" and self._on_stream_start:
                self._on_stream_start(data["channel"], data["coin"], data["total_records"])

            elif msg_type == "stream_progress" and self._on_stream_progress:
                self._on_stream_progress(
                    data["records_sent"], data["total_records"], data["progress_pct"]
                )

            elif msg_type == "historical_batch" and self._on_batch:
                records = [TimestampedRecord(**r) for r in data["records"]]
                self._on_batch(data["coin"], records)

            elif msg_type == "stream_completed" and self._on_stream_complete:
                self._on_stream_complete(data["channel"], data["coin"], data["records_sent"])

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if self._reconnect_attempts >= self.options.max_reconnect_attempts:
            self._set_state("disconnected")
            return

        self._set_state("reconnecting")
        self._reconnect_attempts += 1

        delay = self.options.reconnect_delay * (2 ** (self._reconnect_attempts - 1))
        logger.info(f"Reconnecting in {delay}s (attempt {self._reconnect_attempts})")

        await asyncio.sleep(delay)
        await self._connect()
