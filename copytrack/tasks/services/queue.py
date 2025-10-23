"""Queue management helpers."""
from __future__ import annotations

from django.db.models import QuerySet

from ..models import Task, TaskStatus


def get_waiting_queue() -> QuerySet[Task]:
    return (
        Task.objects.filter(status__in=[TaskStatus.WAITING, TaskStatus.QUEUED])
        .order_by("-urgent", "created_at")
    )


def get_processing_queue() -> QuerySet[Task]:
    return Task.objects.filter(status=TaskStatus.IN_PROGRESS).order_by("start_time")


def get_completed_tasks() -> QuerySet[Task]:
    return Task.objects.filter(status__in=[TaskStatus.COMPLETED, TaskStatus.DELIVERED]).order_by(
        "-finish_time"
    )
