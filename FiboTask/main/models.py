from django.core.validators import MinLengthValidator
from django.db import models


class Task(models.Model):
    title = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(1)],
    )
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"])]

    def __str__(self):
        return self.title
