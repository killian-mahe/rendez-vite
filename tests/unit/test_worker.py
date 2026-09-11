from __future__ import annotations

import pytest

from rendez_vite.config import Settings
from rendez_vite.orchestration import worker as worker_module
from rendez_vite.orchestration.activities import AppointmentActivities


def test_build_activities_wires_the_builtin_adapters(settings):
    activities = worker_module.build_activities(settings)
    assert isinstance(activities, AppointmentActivities)
    assert len(activities.as_list()) == 2


async def test_run_worker_serves_the_configured_task_queue(monkeypatch, settings):
    served: dict[str, object] = {}

    class FakeWorker:
        async def run(self):
            served["ran"] = True

    async def fake_build_client(passed_settings):
        served["settings"] = passed_settings
        return object()

    def fake_build_worker(client, passed_settings):
        served["queue"] = passed_settings.temporal_task_queue
        return FakeWorker()

    monkeypatch.setattr(worker_module, "build_client", fake_build_client)
    monkeypatch.setattr(worker_module, "build_worker", fake_build_worker)
    await worker_module.run_worker(settings)
    assert served["ran"] is True
    assert served["queue"] == settings.temporal_task_queue


async def test_run_worker_falls_back_on_the_process_settings(monkeypatch):
    captured: dict[str, object] = {}

    class FakeWorker:
        async def run(self):
            return None

    async def fake_build_client(passed_settings):
        captured["settings"] = passed_settings
        return object()

    monkeypatch.setattr(worker_module, "build_client", fake_build_client)
    monkeypatch.setattr(worker_module, "build_worker", lambda *_: FakeWorker())
    await worker_module.run_worker()
    assert isinstance(captured["settings"], Settings)


@pytest.mark.parametrize(
    ("tls", "api_key", "expected"),
    [
        (False, None, {}),
        (True, None, {"tls": True}),
        (True, "key", {"tls": True, "api_key": "key"}),
    ],
)
async def test_client_options_follow_the_settings(monkeypatch, tls, api_key, expected):
    from temporalio.client import Client

    from rendez_vite.orchestration.client import build_client

    captured: dict[str, object] = {}

    async def fake_connect(address, **options):
        captured["address"] = address
        captured["options"] = options
        return "client"

    monkeypatch.setattr(Client, "connect", fake_connect)
    settings = Settings(temporal_tls=tls, temporal_api_key=api_key)
    await build_client(settings)
    assert captured["address"] == settings.temporal_address
    assert captured["options"] == {"namespace": "default", **expected}
