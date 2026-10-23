"""Local, organic-first release planning with no publishing or ad execution."""
from __future__ import annotations

from datetime import date, timedelta


TASKS = (
    (
        "confirm_readiness",
        "pre_release",
        -21,
        "Confirm release readiness",
        "Review release timing, recording/composition permissions, deliverables, and any distributor lead times.",
        [],
    ),
    (
        "choose_experiment",
        "pre_release",
        -14,
        "Choose a small audience experiment",
        "Select a relevant listener group yourself and define one question to learn from; do not treat responses as a forecast.",
        ["confirm_readiness"],
    ),
    (
        "draft_content",
        "pre_release",
        -7,
        "Draft the content calendar",
        "Prepare optional organic post ideas and captions for artist review; publishing remains manual.",
        ["choose_experiment"],
    ),
    (
        "final_review",
        "pre_release",
        -1,
        "Review final materials",
        "Check approved audio, artwork, credits, links, and scheduled dates before release day.",
        ["draft_content"],
    ),
    (
        "release_day",
        "release_day",
        0,
        "Release-day check-in",
        "Confirm the release is available through your distributor, then manually share only materials you approve.",
        ["final_review"],
    ),
    (
        "record_observations",
        "post_release",
        7,
        "Record authorized observations",
        "If available, record metrics you are authorized to use together with their source and time window; otherwise note that data is unavailable.",
        ["release_day"],
    ),
    (
        "review_lessons",
        "post_release",
        28,
        "Review lessons and next steps",
        "Compare the observations with your original goal and record context; do not infer causation from a simple before/after change.",
        ["record_observations"],
    ),
)


def build_release_tasks(release_date: date | None) -> list[dict]:
    return [
        {
            "task_id": task_id,
            "stage": stage,
            "title": title,
            "action": action,
            "day_offset": day_offset,
            "planned_date": (
                (release_date + timedelta(days=day_offset)).isoformat()
                if release_date
                else None
            ),
            "depends_on": dependencies,
        }
        for task_id, stage, day_offset, title, action, dependencies in TASKS
    ]
