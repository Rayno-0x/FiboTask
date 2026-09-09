from django import forms
from django.core.validators import MaxValueValidator

from .models import Task


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title"]
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "New Task...", "maxlength": "255", "required": True}
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
