from datetime import date, timedelta

from backend.services.release_planning import build_release_tasks


def test_release_calendar_uses_offsets_without_a_release_date():
    tasks = build_release_tasks(None)

    assert len(tasks) == 7
    assert [task["day_offset"] for task in tasks] == [-21, -14, -7, -1, 0, 7, 28]
    assert all(task["planned_date"] is None for task in tasks)
    assert tasks[1]["depends_on"] == ["confirm_readiness"]


def test_release_calendar_dates_are_relative_to_the_artist_selected_date():
    release_date = date(2030, 6, 15)

    tasks = build_release_tasks(release_date)

    assert tasks[0]["planned_date"] == (release_date - timedelta(days=21)).isoformat()
    assert tasks[4]["planned_date"] == release_date.isoformat()
    assert tasks[-1]["planned_date"] == (release_date + timedelta(days=28)).isoformat()
