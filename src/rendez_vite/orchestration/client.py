"""Temporal client factory."""

from __future__ import annotations

from typing import Any

from temporalio.client import Client

from rendez_vite.config import Settings


async def build_client(settings: Settings) -> Client:
    """Connect a Temporal client using the application settings.

    Parameters
    ----------
    settings
        Application settings holding the target address and namespace.

    Returns
    -------
    temporalio.client.Client
        A connected client.
    """
    options: dict[str, Any] = {"namespace": settings.temporal_namespace}
    if settings.temporal_tls:
        options["tls"] = True
    if settings.temporal_api_key is not None:
        options["api_key"] = settings.temporal_api_key.get_secret_value()
    return await Client.connect(settings.temporal_address, **options)
