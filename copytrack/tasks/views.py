"""User facing views for the CopyTrack modules."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from io import StringIO

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from .forms import (
    CardSwipeForm,
    KioskLoginForm,
    PrintLabelForm,
    ReportFilterForm,
    ScanForm,
    TaskSelectForm,
    UrgencyRequestForm,
)
from .models import Task, TaskEvent
from .services.hardware import HARDWARE_STATUS, CardReaderSimulator, LabelPrinterSimulator
from .services.printing import LabelPrinter
from .services.queue import get_completed_tasks, get_processing_queue, get_waiting_queue
from .services.statistics import calculate_summary, export_to_rows, filter_by_date

PRINTER = LabelPrinter()
CARD_READER_SIMULATOR = CardReaderSimulator()
PRINTER_SIMULATOR = LabelPrinterSimulator()

CARD_READER_SIMULATOR.connect()
PRINTER_SIMULATOR.connect()


def _hardware_status_context() -> dict[str, object]:
    """Provide context used to render hardware status panels."""
    return {
        "card_reader": CARD_READER_SIMULATOR,
        "card_last": CARD_READER_SIMULATOR.last_card,
        "printer": PRINTER_SIMULATOR,
        "printer_pending_jobs": PRINTER_SIMULATOR.pending_jobs(),
        "printer_history": PRINTER_SIMULATOR.history(),
        "hardware_snapshot": HARDWARE_STATUS.snapshot(),
    }


class HomeView(View):
    template_name = "tasks/home.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        waiting = get_waiting_queue()
        processing = get_processing_queue()
        completed = get_completed_tasks()[:5]
        summary = calculate_summary(Task.objects.all())
        return render(
            request,
            self.template_name,
            {
                "waiting": waiting,
                "processing": processing,
                "completed": completed,
                "summary": summary,
            },
        )


class KioskLoginView(View):
    template_name = "tasks/kiosk_login.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        form = KioskLoginForm()
        return self._render(request, form)

    def post(self, request: HttpRequest) -> HttpResponse:
        form = KioskLoginForm(request.POST)
        if form.is_valid():
            card_number = form.cleaned_data["card_number"].strip()
            try:
                CARD_READER_SIMULATOR.simulate_swipe(card_number)
            except RuntimeError as exc:
                messages.error(request, str(exc))
                return self._render(request, form)
            request.session["kiosk_user"] = card_number
            messages.success(request, "刷卡成功，正在跳转取号页面")
            return redirect("tasks:kiosk_tasks")
        return self._render(request, form)

    def _render(self, request: HttpRequest, form: KioskLoginForm) -> HttpResponse:
        context = {"form": form}
        context.update(_hardware_status_context())
        return render(request, self.template_name, context)


class KioskTasksView(View):
    template_name = "tasks/kiosk_tasks.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        user_id = request.session.get("kiosk_user")
        if not user_id:
            messages.warning(request, "请先刷卡登录")
            return redirect("tasks:kiosk_login")
        tasks = Task.objects.filter(user_id=user_id).order_by("-created_at")
        select_form = TaskSelectForm(user_tasks=tasks)
        return render(request, self.template_name, {"tasks": tasks, "select_form": select_form})

    def post(self, request: HttpRequest) -> HttpResponse:
        user_id = request.session.get("kiosk_user")
        tasks = Task.objects.filter(user_id=user_id).order_by("-created_at")
        form = TaskSelectForm(request.POST, user_tasks=tasks)
        if form.is_valid():
            task: Task = form.cleaned_data["task"]
            PRINTER.print_task(task)
            try:
                PRINTER_SIMULATOR.simulate_print(f"任务 {task.task_code} 标签", copies=task.copies)
                messages.success(request, f"任务 {task.task_code} 标签已发送打印")
            except RuntimeError as exc:
                messages.warning(
                    request,
                    f"任务 {task.task_code} 标签已发送打印，但模拟打印机未连接：{exc}",
                )
            return redirect("tasks:kiosk_tasks")
        return render(request, self.template_name, {"tasks": tasks, "select_form": form})


class KioskUrgentView(View):
    template_name = "tasks/kiosk_urgent.html"

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        task = get_object_or_404(Task, pk=pk)
        form = UrgencyRequestForm(initial={"task_id": task.pk, "urgent": True})
        return render(request, self.template_name, {"task": task, "form": form})

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        task = get_object_or_404(Task, pk=pk)
        form = UrgencyRequestForm(request.POST)
        if form.is_valid():
            urgent = form.cleaned_data["urgent"]
            if urgent:
                task.request_urgent()
                messages.success(request, "已提交加急申请")
            else:
                task.cancel_urgent()
                messages.info(request, "已取消加急")
            TaskEvent.log(task, task.status, form.cleaned_data.get("reason", ""))
            return redirect("tasks:kiosk_tasks")
        return render(request, self.template_name, {"task": task, "form": form})


class WebTaskListView(View):
    template_name = "tasks/web_tasks.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        user_id = request.GET.get("user") or request.session.get("web_user")
        if user_id:
            request.session["web_user"] = user_id
            tasks = Task.objects.filter(user_id=user_id).order_by("-created_at")
        else:
            tasks = Task.objects.none()
        return render(request, self.template_name, {"tasks": tasks, "user_id": user_id})


class OperatorConsoleView(View):
    template_name = "tasks/operator_console.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        form = ScanForm()
        context = {
            "form": form,
            "waiting": get_waiting_queue(),
            "processing": get_processing_queue(),
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest) -> HttpResponse:
        form = ScanForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["task_code"]
            action = form.cleaned_data["action"]
            operator = form.cleaned_data["operator"]
            task = get_object_or_404(Task, task_code=code)
            if action == "start":
                task.start()
            elif action == "finish":
                task.finish()
            elif action == "deliver":
                task.deliver()
            TaskEvent.log(task, task.status, f"扫码操作: {action}", operator=operator)
            messages.success(request, f"任务 {task.task_code} 状态已更新")
            return HttpResponseRedirect(reverse("tasks:operator_console"))
        context = {
            "form": form,
            "waiting": get_waiting_queue(),
            "processing": get_processing_queue(),
        }
        return render(request, self.template_name, context)


class ReportView(View):
    template_name = "tasks/reports.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        form = ReportFilterForm(request.GET or None)
        tasks = Task.objects.all().order_by("-created_at")
        if form.is_valid():
            start = form.cleaned_data["start_date"]
            end = form.cleaned_data["end_date"]
            if start:
                start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.get_current_timezone())
            else:
                start_dt = None
            if end:
                end_dt = datetime.combine(end, datetime.max.time(), tzinfo=timezone.get_current_timezone())
            else:
                end_dt = None
            tasks = filter_by_date(tasks, start_dt, end_dt)
            if form.cleaned_data["only_urgent"]:
                tasks = tasks.filter(urgent=True)
        summary = calculate_summary(tasks)
        return render(request, self.template_name, {"form": form, "tasks": tasks[:100], "summary": summary})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = ReportFilterForm(request.POST)
        if form.is_valid():
            tasks = Task.objects.all()
            start = form.cleaned_data["start_date"]
            end = form.cleaned_data["end_date"]
            start_dt = (
                datetime.combine(start, datetime.min.time(), tzinfo=timezone.get_current_timezone())
                if start
                else None
            )
            end_dt = (
                datetime.combine(end, datetime.max.time(), tzinfo=timezone.get_current_timezone())
                if end
                else None
            )
            tasks = filter_by_date(tasks, start_dt, end_dt)
            if form.cleaned_data["only_urgent"]:
                tasks = tasks.filter(urgent=True)
            rows = export_to_rows(tasks)
            buffer = StringIO()
            writer = csv.writer(buffer)
            writer.writerows(rows)
            response = HttpResponse(buffer.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = "attachment; filename=copytrack_report.csv"
            return response
        messages.error(request, "导出参数有误")
        return redirect("tasks:reports")


class HardwareTestView(View):
    template_name = "tasks/hardware_test.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return self._render(request)

    def post(self, request: HttpRequest) -> HttpResponse:
        action = request.POST.get("action")
        card_form: CardSwipeForm | None = None
        print_form: PrintLabelForm | None = None
        try:
            if action == "connect_reader":
                CARD_READER_SIMULATOR.connect()
                messages.success(request, "刷卡机已连接")
            elif action == "disconnect_reader":
                CARD_READER_SIMULATOR.disconnect()
                messages.info(request, "刷卡机已断开并清除最近刷卡记录")
            elif action == "swipe_card":
                card_form = CardSwipeForm(request.POST)
                if card_form.is_valid():
                    card_number = card_form.cleaned_data["card_number"]
                    CARD_READER_SIMULATOR.simulate_swipe(card_number)
                    messages.success(request, f"模拟刷卡成功：{card_number}")
                else:
                    messages.error(request, "请提供有效的刷卡号")
            elif action == "clear_swipe_history":
                CARD_READER_SIMULATOR.clear_history()
                messages.info(request, "刷卡历史已清除")
            elif action == "connect_printer":
                PRINTER_SIMULATOR.connect()
                messages.success(request, "标签打印机已连接")
            elif action == "disconnect_printer":
                PRINTER_SIMULATOR.disconnect()
                messages.info(request, "打印机已断开并清空待处理队列")
            elif action == "print_label":
                print_form = PrintLabelForm(request.POST)
                if print_form.is_valid():
                    content = print_form.cleaned_data["content"]
                    copies = print_form.cleaned_data["copies"]
                    PRINTER_SIMULATOR.simulate_print(content, copies=copies)
                    messages.success(request, "模拟打印任务已加入队列")
                else:
                    messages.error(request, "请检查打印内容和份数")
            elif action == "process_next_job":
                job = PRINTER_SIMULATOR.process_next_job()
                if job:
                    messages.success(request, f"已处理打印任务：{job.content[:20]}...")
                else:
                    messages.info(request, "当前没有待处理的打印任务")
            elif action == "clear_print_history":
                PRINTER_SIMULATOR.clear_history()
                messages.info(request, "打印历史已清除")
        except RuntimeError as exc:
            messages.error(request, str(exc))
        return self._render(
            request,
            card_form=card_form if card_form is not None else CardSwipeForm(),
            print_form=print_form if print_form is not None else PrintLabelForm(),
        )

    def _render(
        self,
        request: HttpRequest,
        *,
        card_form: CardSwipeForm | None = None,
        print_form: PrintLabelForm | None = None,
    ) -> HttpResponse:
        context = {
            "card_reader": CARD_READER_SIMULATOR,
            "printer": PRINTER_SIMULATOR,
            "card_form": card_form or CardSwipeForm(),
            "print_form": print_form or PrintLabelForm(),
            "swipe_history": CARD_READER_SIMULATOR.history(),
            "pending_jobs": PRINTER_SIMULATOR.pending_jobs(),
            "print_history": PRINTER_SIMULATOR.history(),
            "hardware_snapshot": HARDWARE_STATUS.snapshot(),
        }
        return render(request, self.template_name, context)


class HardwareStatusPanelView(View):
    template_name = "tasks/includes/hardware_status_panel.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, self.template_name, _hardware_status_context())


class HardwareStatusStreamView(View):
    """Server-Sent Events endpoint streaming hardware status changes."""

    def get(self, request: HttpRequest) -> StreamingHttpResponse:
        response = StreamingHttpResponse(
            self._event_stream(request),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    def _event_stream(self, request: HttpRequest):
        last_seen = self._parse_last_event_id(request.headers.get("Last-Event-ID"))
        try:
            latest = HARDWARE_STATUS.latest_event()
            if latest and latest["id"] > (last_seen or 0):
                yield _format_sse_event(latest)
                last_seen = latest["id"]
            while True:
                event = HARDWARE_STATUS.wait_for_event(last_seen)
                yield _format_sse_event(event)
                last_seen = event["id"]
        except GeneratorExit:  # connection closed by client
            return

    @staticmethod
    def _parse_last_event_id(header_value: str | None) -> int | None:
        if not header_value:
            return None
        try:
            return int(header_value)
        except (TypeError, ValueError):
            return None


def _format_sse_event(event: dict[str, object]) -> str:
    payload = json.dumps(
        {
            "changed_device": event.get("changed_device"),
            "statuses": event.get("statuses"),
            "timestamp": event.get("timestamp"),
        }
    )
    return f"id: {event['id']}\nevent: hardware-status\ndata: {payload}\n\n"


home = HomeView.as_view()
kiosk_login = KioskLoginView.as_view()
kiosk_tasks = KioskTasksView.as_view()
kiosk_urgent = KioskUrgentView.as_view()
web_tasks = WebTaskListView.as_view()
operator_console = OperatorConsoleView.as_view()
reports = ReportView.as_view()
hardware_test = HardwareTestView.as_view()
hardware_status_panel = HardwareStatusPanelView.as_view()
hardware_status_stream = HardwareStatusStreamView.as_view()
