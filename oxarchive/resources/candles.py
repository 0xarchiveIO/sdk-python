"""Candles API resource."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..http import HttpClient
from ..types import Candle, CandleInterval, Timestamp


class CandlesResource:
    """
    Candles (OHLCV) API resource.

    Example:
        >>> # Get hourly candles
        >>> candles = client.candles.list("BTC", interval="1h")
        >>>
        >>> # Get daily candles for a date range
        >>> daily = client.candles.list("ETH", interval="1d", start="2024-01-01", end="2024-01-31")
    """

    def __init__(self, http: HttpClient):
        self._http = http

    def _convert_timestamp(self, ts: Optional[Timestamp]) -> Optional[int]:
        """Convert timestamp to Unix milliseconds."""
        if ts is None:
            return None
        if isinstance(ts, int):
            return ts
        if isinstance(ts, datetime):
            return int(ts.timestamp() * 1000)
        if isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except ValueError:
                return int(ts)
        return None

    def list(
        self,
        coin: str,
        *,
        interval: Optional[CandleInterval] = None,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[Candle]:
        """
        Get OHLCV candles for a coin.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            interval: Candle interval ('1m', '5m', '15m', '1h', '4h', '1d')
            start: Start timestamp
            end: End timestamp
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of candles
        """
        data = self._http.get(
            f"/v1/candles/{coin.upper()}",
            params={
                "interval": interval,
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "limit": limit,
                "offset": offset,
            },
        )
        return [Candle.model_validate(item) for item in data["data"]]

    async def alist(
        self,
        coin: str,
        *,
        interval: Optional[CandleInterval] = None,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[Candle]:
        """Async version of list()."""
        data = await self._http.aget(
            f"/v1/candles/{coin.upper()}",
            params={
                "interval": interval,
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "limit": limit,
                "offset": offset,
            },
        )
        return [Candle.model_validate(item) for item in data["data"]]
