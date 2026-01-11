"""Open interest API resource."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..http import HttpClient
from ..types import OpenInterest, Timestamp


class OpenInterestResource:
    """
    Open interest API resource.

    Example:
        >>> # Get current open interest
        >>> current = client.open_interest.current("BTC")
        >>>
        >>> # Get open interest history
        >>> history = client.open_interest.history("ETH", start="2024-01-01", end="2024-01-07")
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

    def history(
        self,
        coin: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[OpenInterest]:
        """
        Get open interest history for a coin.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp
            end: End timestamp
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of open interest records
        """
        data = self._http.get(
            f"/v1/openinterest/{coin.upper()}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "limit": limit,
                "offset": offset,
            },
        )
        return [OpenInterest.model_validate(item) for item in data["data"]]

    async def ahistory(
        self,
        coin: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[OpenInterest]:
        """Async version of history()."""
        data = await self._http.aget(
            f"/v1/openinterest/{coin.upper()}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "limit": limit,
                "offset": offset,
            },
        )
        return [OpenInterest.model_validate(item) for item in data["data"]]

    def current(self, coin: str) -> OpenInterest:
        """
        Get current open interest for a coin.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')

        Returns:
            Current open interest
        """
        data = self._http.get(f"/v1/openinterest/{coin.upper()}/current")
        return OpenInterest.model_validate(data["data"])

    async def acurrent(self, coin: str) -> OpenInterest:
        """Async version of current()."""
        data = await self._http.aget(f"/v1/openinterest/{coin.upper()}/current")
        return OpenInterest.model_validate(data["data"])
