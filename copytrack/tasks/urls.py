"""URL configuration for task related endpoints."""
from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.home, name="home"),
    path("kiosk/login/", views.kiosk_login, name="kiosk_login"),
    path("kiosk/tasks/", views.kiosk_tasks, name="kiosk_tasks"),
    path("kiosk/tasks/<int:pk>/urgent/", views.kiosk_urgent, name="kiosk_urgent"),
    path("web/tasks/", views.web_tasks, name="web_tasks"),
    path("operator/", views.operator_console, name="operator_console"),
    path("reports/", views.reports, name="reports"),
    path("hardware/test/", views.hardware_test, name="hardware_test"),
    path("hardware/status/panel/", views.hardware_status_panel, name="hardware_status_panel"),
    path("hardware/status/stream/", views.hardware_status_stream, name="hardware_status_stream"),
]
