"""Minimal logging configuration shared by the worker and the CLI."""

from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger with a single readable handler.

    Parameters
    ----------
    level
        Logging level name, such as ``"INFO"`` or ``"DEBUG"``.
    """
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        force=True,
    )
