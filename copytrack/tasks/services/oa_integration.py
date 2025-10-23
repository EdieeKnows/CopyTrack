"""Integration helpers for synchronising OA approved tasks."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from django.utils import timezone

from ..models import Task, TaskEvent


@dataclass
class ApprovedTask:
    task_code: str
    user_id: str
    user_name: str
    department: str
    copies: int
    description: str


class OASynchroniser:
    """Utility class that creates or updates :class:`Task` objects from OA exports."""

    def sync(self, approved_tasks: Iterable[ApprovedTask]) -> tuple[int, int]:
        created = 0
        updated = 0
        for approved in approved_tasks:
            task, is_created = Task.objects.update_or_create(
                task_code=approved.task_code,
                defaults={
                    "user_id": approved.user_id,
                    "user_name": approved.user_name,
                    "department": approved.department,
                    "copies": approved.copies,
                    "description": approved.description,
                },
            )
            if is_created:
                created += 1
                TaskEvent.log(task, task.status, "OA 同步", operator="OA")
            else:
                updated += 1
        return created, updated

    def sync_from_csv(self, csv_path: Path) -> tuple[int, int]:
        """Load OA approved tasks from a CSV export file."""

        approved: list[ApprovedTask] = []
        with csv_path.open("r", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                approved.append(
                    ApprovedTask(
                        task_code=row["task_code"],
                        user_id=row["user_id"],
                        user_name=row["user_name"],
                        department=row.get("department", ""),
                        copies=int(row.get("copies", 1)),
                        description=row.get("description", ""),
                    )
                )
        return self.sync(approved)


def generate_task_code(prefix: str = "CT") -> str:
    now = timezone.now()
    return f"{prefix}{now:%Y%m%d%H%M%S%f}"
