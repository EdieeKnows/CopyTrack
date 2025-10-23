"""Label printing integration."""
from __future__ import annotations

from dataclasses import dataclass

from ..models import Task


@dataclass
class PrintJob:
    content: str
    copies: int


class LabelPrinter:
    """Simple abstraction layer that would normally communicate with the printer."""

    def __init__(self, queue: list[PrintJob] | None = None) -> None:
        self.queue: list[PrintJob] = queue or []

    def build_job(self, task: Task) -> PrintJob:
        content = f"^XA^FO50,50^BCN,100,Y,N,N^FD{task.task_code}^FS^FO50,170^ADN,36,20^FD{task.user_name}-{task.copies}份^FS^XZ"
        return PrintJob(content=content, copies=1)

    def send(self, job: PrintJob) -> None:
        self.queue.append(job)

    def print_task(self, task: Task) -> None:
        job = self.build_job(task)
        self.send(job)
        task.mark_printed()

    def pending_jobs(self) -> list[PrintJob]:
        return list(self.queue)
