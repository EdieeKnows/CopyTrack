"""Import approved OA tasks from a CSV file."""
from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandParser

from ...services.oa_integration import OASynchroniser


class Command(BaseCommand):
    help = "Import OA 审批通过的复印任务 CSV"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("csv_path", type=str, help="OA导出的CSV文件路径")

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"]).expanduser().resolve()
        syncer = OASynchroniser()
        created, updated = syncer.sync_from_csv(csv_path)
        self.stdout.write(self.style.SUCCESS(f"导入完成，新建 {created} 条，更新 {updated} 条"))
