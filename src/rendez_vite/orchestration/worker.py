"""Worker process hosting the workflow and its activities."""

from __future__ import annotations

import logging

from temporalio.client import Client
from temporalio.worker import Worker

from rendez_vite.config import Settings, get_settings
from rendez_vite.infrastructure.notifiers import build_notifier_registry
from rendez_vite.infrastructure.providers import build_provider_registry
from rendez_vite.infrastructure.rendering import PlainTextAlertRenderer
from rendez_vite.orchestration.activities import AppointmentActivities
from rendez_vite.orchestration.client import build_client
from rendez_vite.orchestration.workflows import RendezViteWatchWorkflow

logger = logging.getLogger(__name__)


def build_activities(settings: Settings) -> AppointmentActivities:
    """Assemble the activity set with the built-in adapters.

    Parameters
    ----------
    settings
        Application settings handed over to the adapter factories.

    Returns
    -------
    AppointmentActivities
        The activity set ready to be registered on a worker.
    """
    return AppointmentActivities(
        providers=build_provider_registry(),
        notifiers=build_notifier_registry(),
        renderer=PlainTextAlertRenderer(),
        settings=settings,
    )


def build_worker(client: Client, settings: Settings) -> Worker:
    """Build the worker polling the configured task queue.

    Parameters
    ----------
    client
        Connected Temporal client.
    settings
        Application settings holding the task queue name.

    Returns
    -------
    temporalio.worker.Worker
        The configured worker.
    """
    return Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[RendezViteWatchWorkflow],
        activities=build_activities(settings).as_list(),
    )


async def run_worker(settings: Settings | None = None) -> None:
    """Connect to Temporal and serve the task queue until interrupted.

    Parameters
    ----------
    settings
        Application settings; loaded from the environment when omitted.
    """
    settings = settings or get_settings()
    client = await build_client(settings)
    logger.info(
        "Worker listening on %s (namespace %s, queue %s)",
        settings.temporal_address,
        settings.temporal_namespace,
        settings.temporal_task_queue,
    )
    await build_worker(client, settings).run()
