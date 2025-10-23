from django.contrib import admin

from .models import Task, TaskEvent


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("task_code", "user_name", "copies", "status", "urgent", "created_at")
    list_filter = ("status", "urgent", "created_at")
    search_fields = ("task_code", "user_id", "user_name")
    ordering = ("-created_at",)


@admin.register(TaskEvent)
class TaskEventAdmin(admin.ModelAdmin):
    list_display = ("task", "status", "note", "operator", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("task__task_code", "note", "operator")
    ordering = ("-created_at",)
