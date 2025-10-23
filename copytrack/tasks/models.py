"""Database models for the CopyTrack system."""
from __future__ import annotations

from django.db import models
from django.utils import timezone


class TaskStatus(models.TextChoices):
    """Lifecycle states for a copy task."""

    WAITING = "waiting", "待取号"
    QUEUED = "queued", "排队中"
    IN_PROGRESS = "in_progress", "处理中"
    COMPLETED = "completed", "完成"
    DELIVERED = "delivered", "已交付"


class Task(models.Model):
    """Represents a copy request that entered the queue."""

    task_code = models.CharField("任务单号", max_length=32, unique=True)
    user_id = models.CharField("用户工号", max_length=32)
    user_name = models.CharField("姓名", max_length=64)
    department = models.CharField("部门", max_length=128, blank=True)
    copies = models.PositiveIntegerField("复印份数", default=1)
    description = models.TextField("摘要", blank=True)
    status = models.CharField(
        "状态",
        max_length=32,
        choices=TaskStatus.choices,
        default=TaskStatus.WAITING,
    )
    urgent = models.BooleanField("加急", default=False)
    created_at = models.DateTimeField("创建时间", default=timezone.now)
    printed_at = models.DateTimeField("标签打印时间", null=True, blank=True)
    start_time = models.DateTimeField("开始时间", null=True, blank=True)
    finish_time = models.DateTimeField("完成时间", null=True, blank=True)
    delivered_at = models.DateTimeField("交付时间", null=True, blank=True)

    class Meta:
        ordering = ["urgent", "created_at"]
        verbose_name = "复印任务"
        verbose_name_plural = "复印任务"

    def mark_printed(self) -> None:
        self.printed_at = timezone.now()
        self.status = TaskStatus.QUEUED
        self.save(update_fields=["printed_at", "status"])
        TaskEvent.log(self, TaskStatus.QUEUED, "标签打印")

    def start(self) -> None:
        self.start_time = timezone.now()
        self.status = TaskStatus.IN_PROGRESS
        self.save(update_fields=["start_time", "status"])
        TaskEvent.log(self, TaskStatus.IN_PROGRESS, "开始复印")

    def finish(self) -> None:
        self.finish_time = timezone.now()
        self.status = TaskStatus.COMPLETED
        self.save(update_fields=["finish_time", "status"])
        TaskEvent.log(self, TaskStatus.COMPLETED, "完成复印")

    def deliver(self) -> None:
        self.delivered_at = timezone.now()
        self.status = TaskStatus.DELIVERED
        self.save(update_fields=["delivered_at", "status"])
        TaskEvent.log(self, TaskStatus.DELIVERED, "交付用户")

    def request_urgent(self) -> None:
        self.urgent = True
        self.save(update_fields=["urgent"])
        TaskEvent.log(self, self.status, "申请加急")

    def cancel_urgent(self) -> None:
        self.urgent = False
        self.save(update_fields=["urgent"])
        TaskEvent.log(self, self.status, "取消加急")

    def __str__(self) -> str:  # pragma: no cover - admin display
        return f"{self.task_code} - {self.user_name}"


class TaskEvent(models.Model):
    """Status change history and operator logs."""

    task = models.ForeignKey(Task, related_name="events", on_delete=models.CASCADE)
    status = models.CharField("状态", max_length=32, choices=TaskStatus.choices)
    note = models.CharField("备注", max_length=255, blank=True)
    created_at = models.DateTimeField("时间", default=timezone.now)
    operator = models.CharField("操作员", max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "任务事件"
        verbose_name_plural = "任务事件"

    def __str__(self) -> str:  # pragma: no cover - admin display
        return f"{self.task.task_code} - {self.get_status_display()}"

    @classmethod
    def log(cls, task: Task, status: str, note: str, operator: str | None = None) -> "TaskEvent":
        return cls.objects.create(task=task, status=status, note=note, operator=operator or "")
