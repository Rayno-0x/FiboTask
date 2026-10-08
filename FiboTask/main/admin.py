from django.contrib import admin

from .models import FocusSession, Subtask, Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "priority", "estimate", "in_sprint", "completed", "due_date", "created_at")
    list_filter = ("completed", "in_sprint", "priority", "estimate", "due_date")
    search_fields = ("title", "notes", "course")
    list_editable = ("completed", "priority", "estimate", "in_sprint")


@admin.register(Subtask)
class SubtaskAdmin(admin.ModelAdmin):
    list_display = ("title", "task", "completed", "created_at")
    list_filter = ("completed",)
    search_fields = ("title",)


@admin.register(FocusSession)
class FocusSessionAdmin(admin.ModelAdmin):
    list_display = ("task", "minutes", "created_at")
    list_filter = ("created_at",)
