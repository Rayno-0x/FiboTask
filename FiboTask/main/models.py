from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models
from django.utils import timezone


class Organization(models.Model):
    """Campus / team container. Nullable everywhere — paid feature, day-one field."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Profile(models.Model):
    """Per-user settings. Auto-created on signup."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    organization = models.ForeignKey(
        Organization, null=True, blank=True, on_delete=models.SET_NULL, related_name="members"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile({self.user})"


class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = "L", "Low"
        MEDIUM = "M", "Medium"
        HIGH = "H", "High"

    # Classic Agile scale — Fibonacci points. None = not estimated yet.
    FIB_POINTS = (1, 2, 3, 5, 8, 13, 21)
    ESTIMATE_CHOICES = [(p, f"{p} pts") for p in FIB_POINTS]
    SNOOZE_STEPS = (1, 2, 3, 5, 8, 13)
    FOCUS_PRESETS = (1, 2, 3, 5, 8, 13, 21, 34)
    # Student-friendly sizing guide: (label, example).
    ESTIMATE_GUIDE = {
        1: ("Micro", "Reply to one message, file one handout"),
        2: ("Quick win", "Pay a fee online, review 5 flashcards"),
        3: ("Standard", "Draft one paragraph, solve one problem-set Q"),
        5: ("Deep work", "Essay draft, full problem set, lab report section"),
        8: ("Too big — split", "Whole assignment → split into 3s and 5s"),
        13: ("Epic — split!", "Exam unit → split into daily 3s/5s"),
        21: ("Project — plan it", "Term paper → milestones across sprints"),
    }

    title = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(1)],
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="tasks",
        help_text="Null only for pre-auth legacy rows.",
    )
    notes = models.TextField(blank=True, default="")
    course = models.CharField(max_length=60, blank=True, default="", help_text="Subject, e.g. Bio 101")
    priority = models.CharField(
        max_length=1, choices=Priority.choices, default=Priority.MEDIUM
    )
    due_date = models.DateField(null=True, blank=True)
    estimate = models.IntegerField(null=True, blank=True, choices=ESTIMATE_CHOICES)
    in_sprint = models.BooleanField(default=False)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["completed", "-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["completed", "-created_at"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["in_sprint"]),
            models.Index(fields=["estimate"]),
            models.Index(fields=["course"]),
            models.Index(fields=["owner", "completed"]),
        ]

    def __str__(self):
        return self.title

    @property
    def is_overdue(self) -> bool:
        if self.completed or not self.due_date:
            return False
        return self.due_date < timezone.localdate()

    @property
    def priority_rank(self) -> int:
        return {"H": 0, "M": 1, "L": 2}.get(self.priority, 1)

    @property
    def needs_split(self) -> bool:
        return (self.estimate or 0) >= 8 and not self.completed

    def subtask_progress(self) -> tuple[int, int]:
        total = self.subtasks.count()
        done = self.subtasks.filter(completed=True).count()
        return done, total


class Subtask(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="subtasks")
    title = models.CharField(max_length=255, validators=[MinLengthValidator(1)])
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["completed", "id"]
        indexes = [models.Index(fields=["task", "completed"])]

    def __str__(self):
        return f"{self.task.title} › {self.title}"


class FocusSession(models.Model):
    """A completed Fibonacci focus block. Task is optional (warm-ups need none)."""

    task = models.ForeignKey(
        Task, null=True, blank=True, on_delete=models.SET_NULL, related_name="focus_sessions"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="focus_sessions"
    )
    minutes = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"]), models.Index(fields=["owner", "-created_at"])]

    def __str__(self):
        label = self.task.title if self.task else "Warm-up"
        return f"{label} · {self.minutes}m"

    @staticmethod
    def suggested_break(work_minutes: int) -> int:
        if work_minutes <= 3:
            return 1
        if work_minutes <= 8:
            return 3
        if work_minutes <= 21:
            return 5
        return 8


class EstimateRecord(models.Model):
    """Calibration dataset: what a task was sized at vs what it cost.

    Written on completion (and backfilled once for legacy rows). The future
    engine reads these — never raw tables — to learn personal min-per-point.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="estimate_records"
    )
    task = models.ForeignKey(Task, null=True, blank=True, on_delete=models.SET_NULL, related_name="estimate_records")
    title = models.CharField(max_length=255, default="")
    estimated = models.IntegerField(null=True, blank=True)
    actual_minutes = models.IntegerField(default=0)
    completed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "-created_at"])]

    def __str__(self):
        return f"{self.title or self.task} · est {self.estimated} · {self.actual_minutes}m"


class SignalEvent(models.Model):
    """Append-only behavioral signals for the prediction engine."""

    class Kind(models.TextChoices):
        FOCUS = "focus", "Focus session"
        SNOOZE = "snooze", "Snoozed"
        SPLIT = "split", "Split added"
        COMPLETE = "complete", "Completed"
        ESTIMATE = "estimate", "Estimated"
        REOPEN = "reopen", "Reopened"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="signal_events"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    task = models.ForeignKey(Task, null=True, blank=True, on_delete=models.SET_NULL, related_name="signal_events")
    minutes = models.IntegerField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "kind", "-created_at"])]

    def __str__(self):
        return f"{self.kind} · {self.task or '-'}"

    @classmethod
    def log(cls, owner, kind, task=None, minutes=None, **meta):
        return cls.objects.create(owner=owner, kind=kind, task=task, minutes=minutes, meta=meta or {})


from django.contrib.auth import get_user_model  # noqa: E402
from django.db.models.signals import post_save  # noqa: E402
from django.dispatch import receiver  # noqa: E402


@receiver(post_save, sender=get_user_model())
def _ensure_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
