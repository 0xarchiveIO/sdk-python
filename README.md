# oxarchive

Official Python SDK for [0xarchive](https://0xarchive.io) - Hyperliquid Historical Data API.

## Installation

```bash
pip install oxarchive
```

## Quick Start

```python
from oxarchive import Client

client = Client(api_key="ox_your_api_key")

# Get current order book
orderbook = client.orderbook.get("BTC")
print(f"BTC mid price: {orderbook.mid_price}")

# Get historical order book snapshots
history = client.orderbook.history(
    "ETH",
    start="2024-01-01",
    end="2024-01-02",
    limit=100
)
```

## Async Support

All methods have async versions prefixed with `a`:

```python
import asyncio
from oxarchive import Client

async def main():
    client = Client(api_key="ox_your_api_key")

    # Async get
    orderbook = await client.orderbook.aget("BTC")
    print(f"BTC mid price: {orderbook.mid_price}")

    # Don't forget to close the client
    await client.aclose()

asyncio.run(main())
```

Or use as async context manager:

```python
async with Client(api_key="ox_your_api_key") as client:
    orderbook = await client.orderbook.aget("BTC")
```

## Configuration

```python
client = Client(
    api_key="ox_your_api_key",      # Required
    base_url="https://api.0xarchive.io",  # Optional
    timeout=30.0,                    # Optional, request timeout in seconds
)
```

## API Reference

### Order Book

```python
# Get current order book
orderbook = client.orderbook.get("BTC")

# Get order book at specific timestamp
historical = client.orderbook.get("BTC", timestamp=1704067200000)

# Get with limited depth
shallow = client.orderbook.get("BTC", depth=10)

# Get historical snapshots
history = client.orderbook.history(
    "BTC",
    start="2024-01-01",
    end="2024-01-02",
    limit=1000
)
```

### Trades

```python
# Get recent trades
recent = client.trades.recent("BTC", limit=100)

# Get trade history
trades = client.trades.list(
    "ETH",
    start="2024-01-01",
    end="2024-01-02",
    side="buy"  # Optional: filter by side
)
```

### Candles (OHLCV)

```python
# Get hourly candles
candles = client.candles.list(
    "BTC",
    interval="1h",
    start="2024-01-01",
    end="2024-01-02"
)

# Available intervals: '1m', '5m', '15m', '1h', '4h', '1d'
```

### Instruments

```python
# List all instruments
instruments = client.instruments.list()

# Get specific instrument
btc = client.instruments.get("BTC")
```

### Funding Rates

```python
# Get current funding rate
current = client.funding.current("BTC")

# Get funding rate history
history = client.funding.history(
    "ETH",
    start="2024-01-01",
    end="2024-01-07"
)
```

### Open Interest

```python
# Get current open interest
current = client.open_interest.current("BTC")

# Get open interest history
history = client.open_interest.history(
    "ETH",
    start="2024-01-01",
    end="2024-01-07"
)
```

## Timestamp Formats

The SDK accepts timestamps in multiple formats:

```python
from datetime import datetime

# Unix milliseconds
client.orderbook.get("BTC", timestamp=1704067200000)

# ISO string
client.orderbook.history("BTC", start="2024-01-01", end="2024-01-02")

# datetime object
client.orderbook.history("BTC", start=datetime(2024, 1, 1), end=datetime(2024, 1, 2))
```

## WebSocket Streaming

For real-time data, install with WebSocket support:

```bash
pip install oxarchive[websocket]
```

### Basic Usage

```python
import asyncio
from oxarchive import OxArchiveWs, WsOptions

async def main():
    ws = OxArchiveWs(WsOptions(api_key="ox_your_api_key"))

    # Set up handlers
    ws.on_open(lambda: print("Connected"))
    ws.on_close(lambda code, reason: print(f"Disconnected: {code}"))
    ws.on_error(lambda e: print(f"Error: {e}"))

    # Connect
    await ws.connect()

    # Subscribe to channels
    ws.subscribe_orderbook("BTC")
    ws.subscribe_orderbook("ETH")
    ws.subscribe_trades("BTC")
    ws.subscribe_all_tickers()

    # Handle orderbook updates
    ws.on_orderbook(lambda coin, data: print(f"{coin}: {data.mid_price}"))

    # Handle trade updates
    ws.on_trades(lambda coin, trades: print(f"{coin}: {len(trades)} trades"))

    # Keep running
    await asyncio.sleep(60)

    # Disconnect
    await ws.disconnect()

asyncio.run(main())
```

### Historical Replay (like Tardis.dev)

Replay historical data with timing preserved:

```python
import asyncio
import time
from oxarchive import OxArchiveWs, WsOptions

async def main():
    ws = OxArchiveWs(WsOptions(api_key="ox_..."))

    # Handle replay data
    ws.on_historical_data(lambda coin, ts, data:
        print(f"{ts}: {data['mid_price']}")
    )

    ws.on_replay_start(lambda ch, coin, total, speed:
        print(f"Starting replay of {total} records at {speed}x")
    )

    ws.on_replay_complete(lambda ch, coin, sent:
        print(f"Replay complete: {sent} records")
    )

    await ws.connect()

    # Start replay at 10x speed
    await ws.replay(
        "orderbook", "BTC",
        start=int(time.time() * 1000) - 86400000,  # 24 hours ago
        speed=10
    )

    # Control playback
    await ws.replay_pause()
    await ws.replay_resume()
    await ws.replay_seek(1704067200000)  # Jump to timestamp
    await ws.replay_stop()

asyncio.run(main())
```

### Bulk Streaming (like Databento)

Fast bulk download for data pipelines:

```python
import asyncio
import time
from oxarchive import OxArchiveWs, WsOptions

async def main():
    ws = OxArchiveWs(WsOptions(api_key="ox_..."))
    all_data = []

    # Handle batched data
    ws.on_batch(lambda coin, records:
        all_data.extend([r.data for r in records])
    )

    ws.on_stream_progress(lambda sent, total, pct:
        print(f"Progress: {pct:.1f}%")
    )

    ws.on_stream_complete(lambda ch, coin, sent:
        print(f"Downloaded {sent} records")
    )

    await ws.connect()

    # Start bulk stream
    await ws.stream(
        "orderbook", "ETH",
        start=int(time.time() * 1000) - 3600000,  # 1 hour ago
        end=int(time.time() * 1000),
        batch_size=1000
    )

    # Stop stream if needed
    await ws.stream_stop()

asyncio.run(main())
```

### Configuration

```python
ws = OxArchiveWs(WsOptions(
    api_key="ox_your_api_key",
    ws_url="wss://ws.0xarchive.io",  # Optional
    auto_reconnect=True,             # Auto-reconnect on disconnect
    reconnect_delay=1.0,             # Initial reconnect delay (seconds)
    max_reconnect_attempts=10,       # Max reconnect attempts
    ping_interval=30.0,              # Keep-alive ping interval (seconds)
))
```

### Available Channels

| Channel | Description | Requires Coin |
|---------|-------------|---------------|
| `orderbook` | L2 order book updates | Yes |
| `trades` | Trade/fill updates | Yes |
| `ticker` | Price and 24h volume | Yes |
| `all_tickers` | All market tickers | No |

## Error Handling

```python
from oxarchive import Client, OxArchiveError

client = Client(api_key="ox_your_api_key")

try:
    orderbook = client.orderbook.get("INVALID")
except OxArchiveError as e:
    print(f"API Error: {e.message}")
    print(f"Status Code: {e.code}")
    print(f"Request ID: {e.request_id}")
```

## Type Hints

Full type hint support with Pydantic models:

```python
from oxarchive import Client, OrderBook, Trade

client = Client(api_key="ox_your_api_key")

orderbook: OrderBook = client.orderbook.get("BTC")
trades: list[Trade] = client.trades.recent("BTC")
```

## Requirements

- Python 3.9+
- httpx
- pydantic

## License

MIT
