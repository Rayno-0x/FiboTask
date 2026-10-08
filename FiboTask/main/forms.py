from django import forms
from django.core.validators import MaxValueValidator

from .models import Subtask, Task


class TaskForm(forms.ModelForm):
    # Allow minimal POSTs like {"title": "..."} (back-compat + API-friendly).
    priority = forms.ChoiceField(
        choices=Task.Priority.choices,
        required=False,
        initial=Task.Priority.MEDIUM,
        widget=forms.Select(attrs={"aria-label": "Priority"}),
    )
    estimate = forms.TypedChoiceField(
        choices=[("", "Pts")] + [(p, str(p)) for p in Task.FIB_POINTS],
        coerce=lambda v: int(v) if v not in (None, "") else None,
        empty_value=None,
        required=False,
        widget=forms.Select(attrs={"aria-label": "Estimate (Fibonacci points)"}),
    )

    class Meta:
        model = Task
        fields = ["title", "course", "priority", "estimate", "due_date", "notes"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "What needs doing? e.g. Bio 101 problem set",
                    "maxlength": "255",
                    "required": True,
                    "autocomplete": "off",
                    "aria-label": "Task title",
                }
            ),
            "course": forms.TextInput(
                attrs={
                    "placeholder": "Course",
                    "maxlength": "60",
                    "autocomplete": "off",
                    "aria-label": "Course or subject",
                }
            ),
            "due_date": forms.DateInput(attrs={"type": "date", "aria-label": "Due date"}),
            "notes": forms.Textarea(
                attrs={
                    "placeholder": "Notes (optional)…",
                    "rows": 2,
                    "maxlength": "2000",
                    "aria-label": "Notes",
                }
            ),
        }

    def clean_priority(self):
        return self.cleaned_data.get("priority") or Task.Priority.MEDIUM

    def clean_course(self):
        return (self.cleaned_data.get("course") or "").strip()[:60]

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if not title:
            raise forms.ValidationError("Title cannot be empty.")
        return title


class SubtaskForm(forms.ModelForm):
    class Meta:
        model = Subtask
        fields = ["title"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "Split it: first small step…",
                    "maxlength": "255",
                    "required": True,
                    "autocomplete": "off",
                    "aria-label": "Subtask title",
                }
            ),
        }

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if not title:
            raise forms.ValidationError("Title cannot be empty.")
        return title


class FibonacciForm(forms.Form):
    n = forms.IntegerField(
        label="Terms",
        min_value=1,
        required=True,
        widget=forms.NumberInput(attrs={"placeholder": "Enter terms (e.g. 10)"}),
    )

    def __init__(self, *args, max_terms=1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["n"].max_value = max_terms
        self.fields["n"].validators.append(
            MaxValueValidator(max_terms, f"Keep it at {max_terms} or fewer terms.")
        )
        self.max_terms = max_terms
