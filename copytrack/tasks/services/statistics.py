"""Reporting utilities for analytics and exports."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from django.db.models import QuerySet

from ..models import Task


@dataclass
class Summary:
    total: int
    urgent: int
    completed: int
    delivered: int


def calculate_summary(tasks: QuerySet[Task]) -> Summary:
    counters = Counter()
    for task in tasks:
        counters["total"] += 1
        if task.urgent:
            counters["urgent"] += 1
        if task.finish_time:
            counters["completed"] += 1
        if task.delivered_at:
            counters["delivered"] += 1
    return Summary(
        total=counters["total"],
        urgent=counters["urgent"],
        completed=counters["completed"],
        delivered=counters["delivered"],
    )


def filter_by_date(tasks: QuerySet[Task], start: datetime | None, end: datetime | None) -> QuerySet[Task]:
    if start:
        tasks = tasks.filter(created_at__gte=start)
    if end:
        tasks = tasks.filter(created_at__lte=end)
    return tasks


def export_to_rows(tasks: Iterable[Task]) -> list[list[str]]:
    rows = [["任务单号", "用户", "份数", "状态", "加急", "创建时间", "完成时间"]]
    for task in tasks:
        rows.append(
            [
                task.task_code,
                task.user_name,
                str(task.copies),
                task.get_status_display(),
                "是" if task.urgent else "否",
                task.created_at.strftime("%Y-%m-%d %H:%M"),
                task.finish_time.strftime("%Y-%m-%d %H:%M") if task.finish_time else "",
            ]
        )
    return rows
