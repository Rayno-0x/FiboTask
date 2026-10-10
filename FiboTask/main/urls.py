from django.urls import path
from django.views.generic.base import RedirectView

from . import views

app_name = "main"

urlpatterns = [
    path("", views.welcome_view, name="welcome"),
    path("welcome/", RedirectView.as_view(url="/", permanent=False)),
    path("tasks/", views.index, name="index"),
    path("edit/<int:pk>/", views.edit_task, name="edit_task"),
    path("complete/<int:pk>/", views.complete_task, name="complete_task"),
    path("delete/<int:pk>/", views.delete_task, name="delete_task"),
    path("clear-completed/", views.clear_completed, name="clear_completed"),
    path("sprint/<int:pk>/", views.toggle_sprint, name="toggle_sprint"),
    path("sprint/clear/", views.clear_sprint, name="clear_sprint"),
    path("sprint/auto/", views.auto_plan, name="auto_plan"),
    path("snooze/<int:pk>/", views.snooze_task, name="snooze_task"),
    path("samples/", views.seed_samples, name="seed_samples"),
    path("export/", views.export_csv, name="export_csv"),
    path("subtasks/<int:pk>/add/", views.subtask_add, name="subtask_add"),
    path("subtasks/<int:pk>/toggle/", views.subtask_toggle, name="subtask_toggle"),
    path("subtasks/<int:pk>/delete/", views.subtask_delete, name="subtask_delete"),
    path("focus/", views.focus_view, name="focus"),
    path("focus/log/", views.focus_log, name="focus_log"),
    path("focus/checkin/", views.focus_checkin, name="focus_checkin"),
    path("command/", views.command_view, name="command"),
    path("guide/", views.guide_view, name="guide"),
    path("fibonacci/create-task/", views.lab_create_task, name="lab_create_task"),
    path("fibonacci/", RedirectView.as_view(url="/command/", permanent=False)),
]
