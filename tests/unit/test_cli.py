from __future__ import annotations

from datetime import UTC, datetime

import pytest

from rendez_vite import cli
from rendez_vite.domain.errors import ConfigurationError
from rendez_vite.domain.models import SearchCriteria, Weekday
from rendez_vite.orchestration.contracts import WatchStatus, WatchSummary


@pytest.mark.parametrize(
    ("value", "expected"), [("30", 30), ("45s", 45), ("15m", 900), ("2h", 7200), (" 1H ", 3600)]
)
def test_parse_duration(value, expected):
    assert cli.parse_duration(value) == expected


@pytest.mark.parametrize("value", ["", "15 minutes", "-5m", "5d"])
def test_parse_duration_rejects_malformed_values(value):
    with pytest.raises(ConfigurationError, match="Invalid duration"):
        cli.parse_duration(value)


def test_parse_weekdays_sorts_and_deduplicates():
    assert cli.parse_weekdays("mer,lun,lun") == [Weekday.MONDAY, Weekday.WEDNESDAY]


def test_parse_weekdays_rejects_an_empty_list():
    with pytest.raises(ConfigurationError, match="At least one weekday"):
        cli.parse_weekdays(" , ")


def test_workflow_id_is_derived_from_the_criteria():
    criteria = SearchCriteria(practitioner_id="Dr House", reason="Première visite !")
    assert cli.default_workflow_id(criteria) == "rendez-vite-dr-house-premi-re-visite"


def parse(argv):
    return cli.build_parser().parse_args(argv)


WATCH_ARGV = [
    "watch",
    "--practitioner",
    "dr-house",
    "--reason",
    "consultation",
    "--email",
    "patient@test.fr",
]


def test_build_watch_request_maps_every_criterion(settings):
    args = parse(
        [
            *WATCH_ARGV,
            "--horizon-days",
            "15",
            "--min-lead-time-hours",
            "12",
            "--weekdays",
            "lun,mar",
            "--from-time",
            "08:00",
            "--to-time",
            "12:00",
            "--timezone",
            "Europe/Paris",
            "--interval",
            "20m",
            "--max-checks",
            "5",
            "--keep-watching",
        ]
    )
    request = cli.build_watch_request(args, settings)
    assert request.criteria.horizon_days == 15
    assert request.criteria.min_lead_time_hours == 12
    assert request.criteria.weekdays == [Weekday.MONDAY, Weekday.TUESDAY]
    assert request.criteria.time_range.start == "08:00"
    assert request.recipient_email == "patient@test.fr"
    assert request.options.check_interval_seconds == 1200
    assert request.options.max_checks == 5
    assert request.options.stop_on_first_match is False


def test_build_watch_request_falls_back_on_the_configured_adapters(settings):
    request = cli.build_watch_request(parse(WATCH_ARGV), settings)
    assert request.options.provider == settings.default_provider
    assert request.options.notifier == settings.default_notifier


def test_build_watch_request_honours_the_adapter_flags(settings):
    args = parse([*WATCH_ARGV, "--provider", "http", "--notifier", "smtp"])
    request = cli.build_watch_request(args, settings)
    assert request.options.provider == "http"
    assert request.options.notifier == "smtp"


class FakeHandle:
    def __init__(self, workflow_id="rendez-vite-dr-house-consultation"):
        self.id = workflow_id
        self.signals: list[object] = []
        self.last_error: str | None = None

    async def result(self):
        return WatchSummary(checks_done=3, notifications_sent=1, stop_reason="matching slot")

    async def query(self, name):
        return WatchStatus(
            criteria=None,
            checks_done=3,
            notifications_sent=1,
            paused=True,
            stop_requested=False,
            last_check=datetime(2026, 3, 2, 9, 0, tzinfo=UTC),
            last_match_count=0,
            last_error=self.last_error,
        )

    async def signal(self, name):
        self.signals.append(name)


class FakeClient:
    def __init__(self):
        self.handle = FakeHandle()
        self.started: dict[str, object] = {}

    async def start_workflow(self, workflow, request, *, id, task_queue):
        self.started = {"request": request, "id": id, "task_queue": task_queue}
        return self.handle

    def get_workflow_handle(self, workflow_id):
        return self.handle


@pytest.fixture
def client(monkeypatch):
    fake = FakeClient()

    async def build_client(_settings):
        return fake

    monkeypatch.setattr(cli, "build_client", build_client)
    return fake


async def test_start_watch_uses_the_derived_workflow_id(client, settings):
    message = await cli.start_watch(parse(WATCH_ARGV), settings)
    assert client.started["id"] == "rendez-vite-dr-house-consultation"
    assert client.started["task_queue"] == settings.temporal_task_queue
    assert "Watch started" in message


async def test_start_watch_accepts_an_explicit_workflow_id(client, settings):
    await cli.start_watch(parse([*WATCH_ARGV, "--workflow-id", "custom"]), settings)
    assert client.started["id"] == "custom"


async def test_start_watch_can_block_until_the_end(client, settings):
    message = await cli.start_watch(parse([*WATCH_ARGV, "--wait"]), settings)
    assert "ended after 3 check(s)" in message
    assert "1 alert(s) sent" in message


async def test_status_describes_a_paused_watch(client, settings):
    message = await cli.show_status(parse(["status", "wf-1"]), settings)
    assert "paused" in message
    assert "3 check(s)" in message


async def test_status_reports_a_tolerated_failure(client, settings):
    client.handle.last_error = "availability lookup: service unavailable"
    message = await cli.show_status(parse(["status", "wf-1"]), settings)
    assert "last error: availability lookup: service unavailable" in message


async def test_stop_sends_the_signal(client, settings):
    message = await cli.stop_watch(parse(["stop", "wf-1"]), settings)
    assert client.handle.signals
    assert "Stop signal sent" in message


def test_components_lists_the_available_adapters():
    described = cli.describe_components()
    assert "providers: fake, http" in described
    assert "notifiers: console, smtp" in described


def test_main_prints_the_components(capsys):
    assert cli.main(["components"]) == 0
    assert "providers:" in capsys.readouterr().out


def test_main_reports_a_configuration_error(capsys):
    exit_code = cli.main([*WATCH_ARGV, "--interval", "nope"])
    assert exit_code == 1
    assert "Error: Invalid duration" in capsys.readouterr().out


def test_main_exits_cleanly_on_interrupt(monkeypatch):
    async def interrupt(_args, _settings):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "dispatch", interrupt)
    assert cli.main(["components"]) == 0


def test_main_runs_the_worker(monkeypatch):
    started = []

    async def fake_worker(settings):
        started.append(settings)

    monkeypatch.setattr(cli, "run_worker", fake_worker)
    assert cli.main(["worker"]) == 0
    assert started


def test_main_dispatches_to_the_watch_command(monkeypatch, client):
    assert cli.main(["--log-level", "DEBUG", *WATCH_ARGV]) == 0


def test_main_dispatches_to_status_and_stop(client):
    assert cli.main(["status", "wf-1"]) == 0
    assert cli.main(["stop", "wf-1"]) == 0
