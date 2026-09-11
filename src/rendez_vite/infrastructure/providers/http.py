"""Generic HTTP adapter reading availabilities from a JSON booking API."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx

from rendez_vite.domain.errors import ConfigurationError, SlotProviderError
from rendez_vite.domain.models import AppointmentSlot, SlotQuery

ClientFactory = Callable[[], httpx.AsyncClient]


class HttpSlotProvider:
    """Read availabilities from a booking API exposing JSON over HTTPS.

    The expected payload is ``{"slots": [{"id", "start", "end", ...}]}`` with ISO-8601
    datetimes; adapting another API means subclassing :meth:`parse_slot`.
    """

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        timeout: float = 10.0,
        client_factory: ClientFactory | None = None,
    ) -> None:
        """Build the provider.

        Parameters
        ----------
        base_url
            Root URL of the booking API.
        token
            Optional bearer token sent on every request.
        timeout
            Per-request timeout in seconds.
        client_factory
            Callable building the HTTP client, overridden in tests.
        """
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._client_factory = client_factory or self._default_client_factory

    def _default_client_factory(self) -> httpx.AsyncClient:
        """Build the HTTP client used in production.

        Returns
        -------
        httpx.AsyncClient
            A client carrying the authentication headers and the timeout.
        """
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        return httpx.AsyncClient(timeout=self._timeout, headers=headers)

    async def fetch_slots(self, query: SlotQuery) -> list[AppointmentSlot]:
        """Return the availabilities advertised by the API for the query window.

        Parameters
        ----------
        query
            Practitioner, reason and time window to look up.

        Returns
        -------
        list of AppointmentSlot
            Slots parsed from the API response.

        Raises
        ------
        SlotProviderError
            If the API is unreachable, answers with an error status or returns a payload
            that cannot be parsed.
        """
        params = {
            "practitioner_id": query.practitioner_id,
            "reason": query.reason,
            "from": query.window_start.isoformat(),
            "to": query.window_end.isoformat(),
        }
        try:
            async with self._client_factory() as client:
                response = await client.get(f"{self._base_url}/availabilities", params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as error:
            raise SlotProviderError(f"Booking API call failed: {error}") from error
        except ValueError as error:
            raise SlotProviderError("Booking API returned a malformed JSON body") from error

        return [self.parse_slot(item, query) for item in self._extract_items(payload)]

    @staticmethod
    def _extract_items(payload: Any) -> list[dict[str, Any]]:
        """Pull the slot entries out of an API payload.

        Parameters
        ----------
        payload
            Decoded JSON body.

        Returns
        -------
        list of dict
            The raw slot entries.

        Raises
        ------
        SlotProviderError
            If the payload does not hold a list of slots.
        """
        items = payload.get("slots") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise SlotProviderError("Booking API response does not contain a list of slots")
        return items

    def parse_slot(self, item: dict[str, Any], query: SlotQuery) -> AppointmentSlot:
        """Convert one API entry into a domain slot.

        Parameters
        ----------
        item
            Raw slot entry.
        query
            Query the entry was returned for, used to fill in missing fields.

        Returns
        -------
        AppointmentSlot
            The parsed appointment.

        Raises
        ------
        SlotProviderError
            If a mandatory field is missing or malformed.
        """
        try:
            start = datetime.fromisoformat(item["start"])
            end = datetime.fromisoformat(item["end"])
            return AppointmentSlot(
                slot_id=str(item.get("id") or f"{query.practitioner_id}:{item['start']}"),
                practitioner_id=str(item.get("practitioner_id") or query.practitioner_id),
                reason=str(item.get("reason") or query.reason),
                start=start,
                end=end,
                location=str(item.get("location") or ""),
                booking_url=str(item.get("booking_url") or ""),
            )
        except (ConfigurationError, KeyError, TypeError, ValueError) as error:
            raise SlotProviderError(f"Unusable slot entry: {item!r}") from error
