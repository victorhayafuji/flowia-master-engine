import os

from packages.scheduling import scheduler


def test_scheduler_disabled_by_env(mocker):
    mocker.patch.object(scheduler, "is_scheduler_enabled", return_value=False)
    result = scheduler.start_scheduler()
    assert result is None


def test_scheduler_starts_jobs(mocker):
    mocker.patch.object(scheduler, "is_scheduler_enabled", return_value=True)
    mock_bg = mocker.patch("packages.scheduling.scheduler.BackgroundScheduler")
    instance = mock_bg.return_value

    scheduler._scheduler = None
    result = scheduler.start_scheduler()

    assert result is instance
    assert instance.add_job.call_count == 2
    instance.start.assert_called_once()
    scheduler.stop_scheduler()


def test_conftest_disables_scheduler():
    assert os.environ.get("SCHEDULER_ENABLED") == "false"
