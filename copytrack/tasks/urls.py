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
]
