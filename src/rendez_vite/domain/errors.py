"""Exception hierarchy shared by every layer of the application."""


class RendezViteError(Exception):
    """Base class for every error raised by Rendez-vite."""


class ConfigurationError(RendezViteError):
    """Raised when the provided configuration or criteria are invalid."""


class UnknownComponentError(ConfigurationError):
    """Raised when a component name cannot be resolved in a registry."""


class SlotProviderError(RendezViteError):
    """Raised when availabilities cannot be retrieved from a booking service."""


class NotificationError(RendezViteError):
    """Raised when a notification cannot be delivered."""
