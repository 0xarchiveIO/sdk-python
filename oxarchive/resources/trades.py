"""Trades API resource."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from ..http import HttpClient
from ..types import Trade, Timestamp


class TradesResource:
    """
    Trades API resource.

    Example:
        >>> # Get recent trades
        >>> trades = client.trades.recent("BTC")
        >>>
        >>> # Get trade history with time range
        >>> history = client.trades.list("ETH", start="2024-01-01", end="2024-01-02")
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
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        side: Optional[Literal["buy", "sell"]] = None,
    ) -> list[Trade]:
        """
        Get trade history for a coin.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp
            end: End timestamp
            limit: Maximum number of results
            offset: Number of results to skip
            side: Filter by trade side

        Returns:
            List of trades
        """
        data = self._http.get(
            f"/v1/trades/{coin.upper()}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "limit": limit,
                "offset": offset,
                "side": side,
            },
        )
        return [Trade.model_validate(item) for item in data["data"]]

    async def alist(
        self,
        coin: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        side: Optional[Literal["buy", "sell"]] = None,
    ) -> list[Trade]:
        """Async version of list()."""
        data = await self._http.aget(
            f"/v1/trades/{coin.upper()}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "limit": limit,
                "offset": offset,
                "side": side,
            },
        )
        return [Trade.model_validate(item) for item in data["data"]]

    def recent(self, coin: str, limit: Optional[int] = None) -> list[Trade]:
        """
        Get most recent trades for a coin.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            limit: Number of trades to return (default: 100)

        Returns:
            List of recent trades
        """
        data = self._http.get(
            f"/v1/trades/{coin.upper()}/recent",
            params={"limit": limit},
        )
        return [Trade.model_validate(item) for item in data["data"]]

    async def arecent(self, coin: str, limit: Optional[int] = None) -> list[Trade]:
        """Async version of recent()."""
        data = await self._http.aget(
            f"/v1/trades/{coin.upper()}/recent",
            params={"limit": limit},
        )
        return [Trade.model_validate(item) for item in data["data"]]
