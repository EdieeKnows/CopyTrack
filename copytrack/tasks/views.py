"""User facing views for the CopyTrack modules."""
from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from .forms import (
    KioskLoginForm,
    ReportFilterForm,
    ScanForm,
    TaskSelectForm,
    UrgencyRequestForm,
)
from .models import Task, TaskEvent
from .services.printing import LabelPrinter
from .services.queue import get_completed_tasks, get_processing_queue, get_waiting_queue
from .services.statistics import calculate_summary, export_to_rows, filter_by_date

PRINTER = LabelPrinter()


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
        return render(request, self.template_name, {"form": form})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = KioskLoginForm(request.POST)
        if form.is_valid():
            request.session["kiosk_user"] = form.cleaned_data["card_number"].strip()
            return redirect("tasks:kiosk_tasks")
        return render(request, self.template_name, {"form": form})


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
            messages.success(request, f"任务 {task.task_code} 标签已发送打印")
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


home = HomeView.as_view()
kiosk_login = KioskLoginView.as_view()
kiosk_tasks = KioskTasksView.as_view()
kiosk_urgent = KioskUrgentView.as_view()
web_tasks = WebTaskListView.as_view()
operator_console = OperatorConsoleView.as_view()
reports = ReportView.as_view()
