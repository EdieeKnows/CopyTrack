from __future__ import annotations

from django.test import TestCase

from .models import Task, TaskStatus
from .services.oa_integration import ApprovedTask, OASynchroniser


class OASynchroniserTests(TestCase):
    def test_sync_creates_tasks(self) -> None:
        syncer = OASynchroniser()
        approved = [
            ApprovedTask(
                task_code="CT001",
                user_id="1001",
                user_name="张三",
                department="行政部",
                copies=10,
                description="资料复印",
            )
        ]
        created, updated = syncer.sync(approved)
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        task = Task.objects.get(task_code="CT001")
        self.assertEqual(task.status, TaskStatus.WAITING)

    def test_sync_updates_existing(self) -> None:
        Task.objects.create(
            task_code="CT002",
            user_id="1002",
            user_name="李四",
            department="财务部",
            copies=5,
        )
        syncer = OASynchroniser()
        approved = [
            ApprovedTask(
                task_code="CT002",
                user_id="1002",
                user_name="李四",
                department="财务部",
                copies=6,
                description="资料补充",
            )
        ]
        created, updated = syncer.sync(approved)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        task = Task.objects.get(task_code="CT002")
        self.assertEqual(task.copies, 6)
