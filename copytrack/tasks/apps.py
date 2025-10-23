from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "copytrack.tasks"
    verbose_name = "复印任务管理"
