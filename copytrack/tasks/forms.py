"""Forms used by the CopyTrack UI modules."""
from __future__ import annotations

from django import forms

from .models import Task


class KioskLoginForm(forms.Form):
    card_number = forms.CharField(label="刷卡号", max_length=64)


class TaskSelectForm(forms.Form):
    task = forms.ModelChoiceField(label="选择任务", queryset=Task.objects.none())

    def __init__(self, *args, **kwargs):
        user_tasks = kwargs.pop("user_tasks", Task.objects.none())
        super().__init__(*args, **kwargs)
        self.fields["task"].queryset = user_tasks


class UrgencyRequestForm(forms.Form):
    task_id = forms.IntegerField(widget=forms.HiddenInput)
    urgent = forms.BooleanField(label="申请加急", required=False, initial=True)
    reason = forms.CharField(label="原因", widget=forms.Textarea, required=False)


class ScanForm(forms.Form):
    task_code = forms.CharField(label="任务单号", max_length=32)
    action = forms.ChoiceField(
        label="操作",
        choices=(
            ("start", "开始处理"),
            ("finish", "完成复印"),
            ("deliver", "完成交付"),
        ),
    )
    operator = forms.CharField(label="操作员", max_length=64)


class ReportFilterForm(forms.Form):
    start_date = forms.DateField(label="开始日期", required=False)
    end_date = forms.DateField(label="结束日期", required=False)
    only_urgent = forms.BooleanField(label="仅显示加急", required=False)


class CardSwipeForm(forms.Form):
    card_number = forms.CharField(label="模拟刷卡号", max_length=64)


class PrintLabelForm(forms.Form):
    content = forms.CharField(label="打印内容", widget=forms.Textarea, required=True)
    copies = forms.IntegerField(label="份数", min_value=1, max_value=5, initial=1)
