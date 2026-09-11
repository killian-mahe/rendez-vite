"""Turn matching slots into a readable e-mail."""

from __future__ import annotations

from rendez_vite.domain.models import AppointmentSlot, EmailMessage, SlotAlert

_FRENCH_DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_FRENCH_MONTHS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


class PlainTextAlertRenderer:
    """Render an alert as a plain-text e-mail in French.

    Dates are formatted without relying on the system locale so that the output stays
    identical on a laptop and inside a container.
    """

    def render(self, alert: SlotAlert) -> EmailMessage:
        """Render the alert.

        Parameters
        ----------
        alert
            Recipient, criteria and matching slots.

        Returns
        -------
        EmailMessage
            Subject and body ready to be sent.
        """
        count = len(alert.slots)
        noun = "créneaux disponibles" if count > 1 else "créneau disponible"
        verb = "correspondent" if count > 1 else "correspond"
        subject = f"Rendez-vite : {count} {noun} ({alert.criteria.reason})"
        lines = [
            f"Bonne nouvelle : {count} {noun} {verb} à vos critères.",
            "",
            f"Praticien : {alert.criteria.practitioner_id}",
            f"Motif : {alert.criteria.reason}",
            "",
        ]
        lines += [self._format_slot(slot, alert.criteria.timezone) for slot in alert.slots]
        lines += [
            "",
            "Pensez à réserver rapidement, ces créneaux partent vite.",
            "-- Rendez-vite",
        ]
        return EmailMessage(recipient=alert.recipient, subject=subject, body="\n".join(lines))

    @staticmethod
    def _format_slot(slot: AppointmentSlot, timezone: str) -> str:
        """Format a single slot as a bullet line.

        Parameters
        ----------
        slot
            Slot to describe.
        timezone
            Timezone the date is displayed in.

        Returns
        -------
        str
            The formatted line.
        """
        start = slot.local_start(timezone)
        date = (
            f"{_FRENCH_DAYS[start.weekday()]} {start.day} "
            f"{_FRENCH_MONTHS[start.month - 1]} {start.year}"
        )
        line = f"- {date} à {start:%H:%M}"
        if slot.location:
            line += f" ({slot.location})"
        if slot.booking_url:
            line += f"\n  Réserver : {slot.booking_url}"
        return line
