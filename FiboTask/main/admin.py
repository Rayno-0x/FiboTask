from django.contrib import admin

from .models import EstimateRecord, FocusSession, Organization, Profile, SignalEvent, Subtask, Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "course", "priority", "estimate", "in_sprint", "completed", "due_date", "created_at")
    list_filter = ("completed", "in_sprint", "priority", "estimate", "due_date")
    search_fields = ("title", "notes", "course", "owner__username")
    list_editable = ("completed", "priority", "estimate", "in_sprint")


@admin.register(Subtask)
class SubtaskAdmin(admin.ModelAdmin):
    list_display = ("title", "task", "completed", "created_at")
    list_filter = ("completed",)
    search_fields = ("title",)


@admin.register(FocusSession)
class FocusSessionAdmin(admin.ModelAdmin):
    list_display = ("task", "owner", "minutes", "created_at")
    list_filter = ("created_at",)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "created_at")
    list_filter = ("organization",)


@admin.register(EstimateRecord)
class EstimateRecordAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "estimated", "actual_minutes", "completed", "created_at")
    list_filter = ("completed", "estimated")


@admin.register(SignalEvent)
class SignalEventAdmin(admin.ModelAdmin):
    list_display = ("kind", "owner", "task", "minutes", "created_at")
    list_filter = ("kind", "created_at")
