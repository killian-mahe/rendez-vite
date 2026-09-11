"""Name-based registry used to select an adapter at runtime."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

from rendez_vite.config import Settings
from rendez_vite.domain.errors import UnknownComponentError

T = TypeVar("T")

ComponentFactory = Callable[[Settings], T]


class ComponentRegistry(Generic[T]):
    """Map adapter names to the factories able to build them.

    Adding an integration means registering a new factory, never editing the callers.
    """

    def __init__(self, kind: str) -> None:
        """Build an empty registry.

        Parameters
        ----------
        kind
            Human readable name of the family of adapters, used in error messages.
        """
        self._kind = kind
        self._factories: dict[str, ComponentFactory[T]] = {}

    def register(self, name: str, factory: ComponentFactory[T]) -> None:
        """Add or replace a factory.

        Parameters
        ----------
        name
            Key used to select the adapter, case insensitive.
        factory
            Callable building the adapter from the settings.
        """
        self._factories[name.lower()] = factory

    def create(self, name: str, settings: Settings) -> T:
        """Build the adapter registered under a name.

        Parameters
        ----------
        name
            Key of the adapter, case insensitive.
        settings
            Settings handed over to the factory.

        Returns
        -------
        T
            The freshly built adapter.

        Raises
        ------
        UnknownComponentError
            If no factory is registered under that name.
        """
        try:
            factory = self._factories[name.lower()]
        except KeyError:
            known = ", ".join(self.names) or "none"
            raise UnknownComponentError(
                f"Unknown {self._kind} {name!r}; registered: {known}"
            ) from None
        return factory(settings)

    @property
    def names(self) -> list[str]:
        """Return the registered names, sorted alphabetically."""
        return sorted(self._factories)
