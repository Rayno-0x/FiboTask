"""Backfill EstimateRecord for legacy completed tasks (pre-auth dataset seed)."""

from django.db import migrations
from django.db.models import Sum


def backfill_estimates(apps, schema_editor):
    Task = apps.get_model("main", "Task")
    EstimateRecord = apps.get_model("main", "EstimateRecord")
    done = (
        Task.objects.filter(completed=True, estimate__isnull=False)
        .annotate(focus_min=Sum("focus_sessions__minutes"))
        .order_by("id")
    )
    EstimateRecord.objects.bulk_create(
        [
            EstimateRecord(
                owner_id=t.owner_id,
                task_id=t.id,
                title=t.title[:255],
                estimated=t.estimate,
                actual_minutes=t.focus_min or 0,
                completed=True,
            )
            for t in done
        ],
        batch_size=500,
    )


def unfill_estimates(apps, schema_editor):
    apps.get_model("main", "EstimateRecord").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("main", "0006_estimaterecord_organization_profile_signalevent_and_more")]

    operations = [migrations.RunPython(backfill_estimates, unfill_estimates)]
