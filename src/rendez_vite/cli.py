"""Command line entry points: run a worker, start, inspect or stop a watch."""

from __future__ import annotations

import argparse
import asyncio
import re
from collections.abc import Sequence

from rendez_vite.config import Settings, get_settings
from rendez_vite.domain.errors import ConfigurationError, RendezViteError
from rendez_vite.domain.models import SearchCriteria, TimeOfDayRange, Weekday
from rendez_vite.infrastructure.notifiers import build_notifier_registry
from rendez_vite.infrastructure.providers import build_provider_registry
from rendez_vite.logging_setup import configure_logging
from rendez_vite.orchestration.client import build_client
from rendez_vite.orchestration.contracts import WatchOptions, WatchRequest
from rendez_vite.orchestration.worker import run_worker
from rendez_vite.orchestration.workflows import RendezViteWatchWorkflow

_DURATION_PATTERN = re.compile(r"^(?P<value>\d+)(?P<unit>[smh])?$")
_DURATION_UNITS = {"s": 1, "m": 60, "h": 3600}
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def parse_duration(value: str) -> int:
    """Parse a duration such as ``30s``, ``15m`` or ``2h`` into seconds.

    Parameters
    ----------
    value
        Duration with an optional ``s``, ``m`` or ``h`` suffix; bare numbers are seconds.

    Returns
    -------
    int
        The duration in seconds.

    Raises
    ------
    ConfigurationError
        If the duration cannot be parsed.
    """
    match = _DURATION_PATTERN.match(value.strip().lower())
    if match is None:
        raise ConfigurationError(f"Invalid duration: {value!r}")
    return int(match["value"]) * _DURATION_UNITS[match["unit"] or "s"]


def parse_weekdays(value: str) -> list[Weekday]:
    """Parse a comma-separated list of weekdays.

    Parameters
    ----------
    value
        Days such as ``"lun,mar,mer"`` or ``"mon,tue"``.

    Returns
    -------
    list of Weekday
        The parsed days, sorted and deduplicated.

    Raises
    ------
    ConfigurationError
        If the list is empty or holds an unknown day.
    """
    days = {Weekday.parse(part) for part in value.split(",") if part.strip()}
    if not days:
        raise ConfigurationError("At least one weekday must be selected")
    return sorted(days)


def default_workflow_id(criteria: SearchCriteria) -> str:
    """Derive a stable workflow identifier from the criteria.

    Two watches with the same practitioner and reason share an identifier, which keeps
    Temporal from running duplicates.

    Parameters
    ----------
    criteria
        The user's search criteria.

    Returns
    -------
    str
        The workflow identifier.
    """
    slug = _SLUG_PATTERN.sub("-", f"{criteria.practitioner_id} {criteria.reason}".lower())
    return f"rendez-vite-{slug.strip('-')}"


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser.

    Returns
    -------
    argparse.ArgumentParser
        The parser exposing the ``worker``, ``watch``, ``status``, ``stop`` and
        ``components`` commands.
    """
    parser = argparse.ArgumentParser(prog="rendez-vite", description=__doc__)
    parser.add_argument("--log-level", default=None, help="Override the configured log level")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("worker", help="Run a Temporal worker")
    commands.add_parser("components", help="List the available providers and notifiers")

    watch = commands.add_parser("watch", help="Start watching a practitioner's agenda")
    watch.add_argument("--practitioner", required=True, help="Practitioner identifier")
    watch.add_argument("--reason", required=True, help="Consultation reason")
    watch.add_argument("--email", required=True, help="Address the alerts are sent to")
    watch.add_argument("--horizon-days", type=int, default=30, help="Search horizon in days")
    watch.add_argument(
        "--min-lead-time-hours", type=int, default=0, help="Ignore slots happening sooner"
    )
    watch.add_argument("--weekdays", default="mon,tue,wed,thu,fri", help="Accepted weekdays")
    watch.add_argument("--from-time", default="00:00", help="Earliest acceptable start (HH:MM)")
    watch.add_argument("--to-time", default="23:59", help="Latest acceptable start (HH:MM)")
    watch.add_argument("--timezone", default="Europe/Paris", help="Timezone of the criteria")
    watch.add_argument("--interval", default="15m", help="Delay between two checks")
    watch.add_argument("--max-checks", type=int, default=None, help="Give up after N checks")
    watch.add_argument("--provider", default=None, help="Booking service adapter")
    watch.add_argument("--notifier", default=None, help="Notification channel")
    watch.add_argument(
        "--keep-watching",
        action="store_true",
        help="Keep looking for further slots after the first alert",
    )
    watch.add_argument("--workflow-id", default=None, help="Override the workflow identifier")
    watch.add_argument("--wait", action="store_true", help="Block until the watch ends")

    for name, help_text in (("status", "Show a watch progress"), ("stop", "Stop a watch")):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("workflow_id", help="Identifier returned by the watch command")

    return parser


def build_watch_request(args: argparse.Namespace, settings: Settings) -> WatchRequest:
    """Turn parsed arguments into a workflow request.

    Parameters
    ----------
    args
        Parsed ``watch`` arguments.
    settings
        Application settings providing the adapter defaults.

    Returns
    -------
    WatchRequest
        The validated request to start the workflow with.
    """
    criteria = SearchCriteria(
        practitioner_id=args.practitioner,
        reason=args.reason,
        timezone=args.timezone,
        horizon_days=args.horizon_days,
        min_lead_time_hours=args.min_lead_time_hours,
        weekdays=parse_weekdays(args.weekdays),
        time_range=TimeOfDayRange(start=args.from_time, end=args.to_time),
    )
    options = WatchOptions(
        check_interval_seconds=parse_duration(args.interval),
        stop_on_first_match=not args.keep_watching,
        max_checks=args.max_checks,
        provider=args.provider or settings.default_provider,
        notifier=args.notifier or settings.default_notifier,
    )
    return WatchRequest(criteria=criteria, recipient_email=args.email, options=options)


async def start_watch(args: argparse.Namespace, settings: Settings) -> str:
    """Start the watch workflow and report its identifier.

    Parameters
    ----------
    args
        Parsed ``watch`` arguments.
    settings
        Application settings.

    Returns
    -------
    str
        Human readable outcome of the command.
    """
    request = build_watch_request(args, settings)
    workflow_id = args.workflow_id or default_workflow_id(request.criteria)
    client = await build_client(settings)
    handle = await client.start_workflow(
        RendezViteWatchWorkflow.run,
        request,
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )
    if not args.wait:
        return f"Watch started: {handle.id}"
    summary = await handle.result()
    return (
        f"Watch {handle.id} ended after {summary.checks_done} check(s): "
        f"{summary.stop_reason} ({summary.notifications_sent} alert(s) sent)"
    )


async def show_status(args: argparse.Namespace, settings: Settings) -> str:
    """Query a running watch and describe its progress.

    Parameters
    ----------
    args
        Parsed ``status`` arguments.
    settings
        Application settings.

    Returns
    -------
    str
        Human readable snapshot of the watch.
    """
    client = await build_client(settings)
    handle = client.get_workflow_handle(args.workflow_id)
    status = await handle.query(RendezViteWatchWorkflow.status)
    state = "paused" if status.paused else "running"
    message = (
        f"{args.workflow_id}: {state}, {status.checks_done} check(s), "
        f"{status.notifications_sent} alert(s), last check {status.last_check}"
    )
    if status.last_error:
        message += f", last error: {status.last_error}"
    return message


async def stop_watch(args: argparse.Namespace, settings: Settings) -> str:
    """Ask a running watch to stop.

    Parameters
    ----------
    args
        Parsed ``stop`` arguments.
    settings
        Application settings.

    Returns
    -------
    str
        Human readable confirmation.
    """
    client = await build_client(settings)
    handle = client.get_workflow_handle(args.workflow_id)
    await handle.signal(RendezViteWatchWorkflow.stop)
    return f"Stop signal sent to {args.workflow_id}"


def describe_components() -> str:
    """List the adapters the worker can select at runtime.

    Returns
    -------
    str
        One line per family of adapters.
    """
    providers = ", ".join(build_provider_registry().names)
    notifiers = ", ".join(build_notifier_registry().names)
    return f"providers: {providers}\nnotifiers: {notifiers}"


async def dispatch(args: argparse.Namespace, settings: Settings) -> str | None:
    """Run the command selected on the command line.

    Parameters
    ----------
    args
        Parsed arguments.
    settings
        Application settings.

    Returns
    -------
    str or None
        The message to print, if any.
    """
    if args.command == "worker":
        await run_worker(settings)
        return None
    if args.command == "watch":
        return await start_watch(args, settings)
    if args.command == "status":
        return await show_status(args, settings)
    if args.command == "stop":
        return await stop_watch(args, settings)
    return describe_components()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line interface.

    Parameters
    ----------
    argv
        Arguments to parse; ``sys.argv`` is used when omitted.

    Returns
    -------
    int
        Process exit code, ``0`` on success and ``1`` on a handled error.
    """
    args = build_parser().parse_args(argv)
    settings = get_settings()
    configure_logging(args.log_level or settings.log_level)
    try:
        message = asyncio.run(dispatch(args, settings))
    except KeyboardInterrupt:
        return 0
    except RendezViteError as error:
        print(f"Error: {error}")
        return 1
    if message:
        print(message)
    return 0
