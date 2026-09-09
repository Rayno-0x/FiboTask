from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import FibonacciForm, TaskForm
from .models import Task
from .utils import fibonacci_series


def index(request):
    tasks_qs = Task.objects.all()
    paginator = Paginator(tasks_qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    form = TaskForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Task added.")
            return redirect("main:index")
        messages.error(request, "Could not add task. Title cannot be empty.")

    return render(request, "main/index.html", {"form": form, "page_obj": page_obj})


@require_POST
def complete_task(request, pk):
    task = get_object_or_404(Task, pk=pk)
    task.completed = not task.completed  # toggle so "Done" is reversible
    task.save(update_fields=["completed", "updated_at"])
    messages.success(request, f"Task '{task.title}' updated.")
    return redirect("main:index")


@require_POST
def delete_task(request, pk):
    task = get_object_or_404(Task, pk=pk)
    task.delete()
    messages.success(request, "Task deleted.")
    return redirect("main:index")


def fibonacci_view(request):
    max_terms = getattr(settings, "FIBONACCI_MAX_TERMS", 1000)
    form = FibonacciForm(request.GET or None, max_terms=max_terms)
    series: list[int] = []
    n = None
    if request.GET and form.is_valid():
        n = form.cleaned_data["n"]
        series = fibonacci_series(n)
    elif request.GET:
        messages.error(request, f"Enter a whole number between 1 and {max_terms}.")
    return render(
        request,
        "main/fibonacci.html",
        {"form": form, "series": series, "n": n, "max_terms": max_terms},
    )
