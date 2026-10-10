from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Case, Count, Q, Sum, When
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import FibonacciForm, SubtaskForm, TaskForm
from .models import EstimateRecord, FocusSession, SignalEvent, Subtask, Task
from .utils import fibonacci_series

VALID_STATUS = {"all", "active", "done", "overdue", "sprint", "today"}
VALID_SORT = {"newest", "oldest", "due", "priority", "title", "points"}


def _today_focus(user) -> dict:
    from django.utils import timezone

    today = timezone.localdate()
    qs = FocusSession.objects.filter(owner=user, created_at__date=today)
    return {
        "sessions": qs.count(),
        "minutes": qs.aggregate(s=Sum("minutes"))["s"] or 0,
    }


def _week_focus(user) -> dict:
    from datetime import timedelta

    from django.utils import timezone

    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())
    qs = FocusSession.objects.filter(owner=user, created_at__date__gte=monday)
    return {
        "sessions": qs.count(),
        "minutes": qs.aggregate(s=Sum("minutes"))["s"] or 0,
    }


def _capacity(request) -> int:
    """Sprint capacity in points, persisted in session. Clamped to a Fib number."""
    try:
        cap = int(request.GET.get("capacity", request.session.get("sprint_capacity", 21)))
    except (TypeError, ValueError):
        cap = 21
    if cap not in Task.FIB_POINTS and cap not in (34, 55):
        cap = 21 if cap > 21 else min(Task.FIB_POINTS, key=lambda p: abs(p - cap))
    request.session["sprint_capacity"] = cap
    return cap


def _sprint_stats(capacity: int, user) -> dict:
    base = Task.objects.filter(owner=user)
    agg = base.filter(in_sprint=True).aggregate(
        count=Count("id"),
        total=Sum("estimate"),
        done=Count("id", filter=Q(completed=True)),
        done_pts=Sum("estimate", filter=Q(completed=True)),
    )
    total = agg["total"] or 0
    done_pts = agg["done_pts"] or 0
    velocity = base.filter(completed=True).aggregate(v=Sum("estimate"))["v"] or 0
    backlog_pts = base.filter(completed=False, in_sprint=False).aggregate(v=Sum("estimate"))["v"] or 0
    pct = round(done_pts / total * 100) if total else 0
    load = round(total / capacity * 100) if capacity else 0
    return {
        "count": agg["count"] or 0,
        "total": total,
        "done": agg["done"] or 0,
        "done_pts": done_pts,
        "pct": pct,
        "load": min(load, 100),
        "over": total > capacity,
        "capacity": capacity,
        "velocity": velocity,
        "backlog_pts": backlog_pts,
    }


def _filter_tasks(request):
    qs = Task.objects.filter(owner=request.user).prefetch_related("subtasks")
    q = (request.GET.get("q") or "").strip()
    status = request.GET.get("status", "all")
    sort = request.GET.get("sort", "newest")
    course = (request.GET.get("course") or "").strip()

    if status not in VALID_STATUS:
        status = "all"
    if sort not in VALID_SORT:
        sort = "newest"

    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(notes__icontains=q) | Q(course__icontains=q))
    if course:
        qs = qs.filter(course__iexact=course)
    if status == "active":
        qs = qs.filter(completed=False)
    elif status == "done":
        qs = qs.filter(completed=True)
    elif status == "sprint":
        qs = qs.filter(in_sprint=True)
    elif status == "today":
        from django.utils import timezone

        today = timezone.localdate()
        qs = qs.filter(completed=False).filter(Q(due_date__lte=today) | Q(due_date__isnull=True))
    elif status == "overdue":
        from django.utils import timezone

        qs = qs.filter(completed=False, due_date__lt=timezone.localdate())

    if sort == "newest":
        qs = qs.order_by("completed", "-created_at")
    elif sort == "oldest":
        qs = qs.order_by("completed", "created_at")
    elif sort == "due":
        qs = qs.order_by("completed", "due_date", "-created_at")
    elif sort == "priority":
        qs = qs.annotate(
            _prank=Case(
                When(priority="H", then=0),
                When(priority="M", then=1),
                When(priority="L", then=2),
                default=1,
            )
        ).order_by("completed", "_prank", "-created_at")
    elif sort == "points":
        qs = qs.order_by("completed", "-estimate", "-created_at")
    elif sort == "title":
        qs = qs.order_by("completed", "title")

    return qs, {"q": q, "status": status, "sort": sort, "course": course}


@login_required
def index(request):
    capacity = _capacity(request)
    tasks_qs, filters = _filter_tasks(request)
    paginator = Paginator(tasks_qs, 8)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    form = TaskForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            task = form.save(commit=False)
            task.owner = request.user
            task.save()
            if task.estimate:
                SignalEvent.log(request.user, SignalEvent.Kind.ESTIMATE, task=task, minutes=task.estimate)
            pts = f", {task.estimate} pts" if task.estimate else ""
            messages.success(request, f"Task “{task.title}” added{pts}.")
            return redirect("main:index")
        messages.error(request, "Could not add task. Check the title.")

    mine = Task.objects.filter(owner=request.user)
    agg = mine.aggregate(
        total=Count("id"),
        done=Count("id", filter=Q(completed=True)),
        active=Count("id", filter=Q(completed=False)),
    )
    total = agg["total"] or 0
    done = agg["done"] or 0
    active = agg["active"] or 0
    pct = round(done / total * 100) if total else 0

    # Preserve filters in pagination links.
    base_qs = "".join(
        f"&{k}={v}"
        for k, v in filters.items()
        if v and not (k == "status" and v == "all") and not (k == "sort" and v == "newest")
    )
    if filters["q"]:
        from urllib.parse import quote

        base_qs = base_qs.replace(f"&q={filters['q']}", f"&q={quote(filters['q'])}")
    if filters.get("course"):
        from urllib.parse import quote

        base_qs = base_qs.replace(
            f"&course={filters['course']}", f"&course={quote(filters['course'])}"
        )

    editing_id = request.GET.get("edit")
    edit_form = None
    if editing_id:
        try:
            edit_task = Task.objects.get(pk=int(editing_id), owner=request.user)
            edit_form = TaskForm(instance=edit_task)
        except (Task.DoesNotExist, ValueError):
            editing_id = None

    try:
        open_id = int(request.GET.get("open", 0) or 0)
    except (TypeError, ValueError):
        open_id = 0
    courses = list(
        Task.objects.filter(owner=request.user).exclude(course="").values_list("course", flat=True).distinct().order_by("course")[:20]
    )

    return render(
        request,
        "main/index.html",
        {
            "form": form,
            "page_obj": page_obj,
            "filters": filters,
            "base_qs": base_qs,
            "stats": {"total": total, "done": done, "active": active, "pct": pct},
            "sprint": _sprint_stats(capacity, request.user),
            "fib_points": Task.FIB_POINTS,
            "estimate_guide": Task.ESTIMATE_GUIDE,
            "courses": courses,
            "focus_today": _today_focus(request.user),
            "open_id": open_id,
            "editing_id": int(editing_id) if editing_id else None,
            "edit_form": edit_form,
        },
    )


@login_required
def edit_task(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, f"Task “{task.title}” updated.")
            return redirect("main:index")
        messages.error(request, "Could not save changes.")
    # GET (?edit=pk) renders index with inline editor open.
    url = f"{redirect('main:index').url}?edit={task.pk}"
    return redirect(url)


@login_required
@require_POST
def complete_task(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    task.completed = not task.completed  # toggle so "Done" is reversible
    task.save(update_fields=["completed", "updated_at"])
    if task.completed:
        actual = task.focus_sessions.aggregate(s=Sum("minutes"))["s"] or 0
        EstimateRecord.objects.create(
            owner=request.user,
            task=task,
            title=task.title[:255],
            estimated=task.estimate,
            actual_minutes=actual,
            completed=True,
        )
        SignalEvent.log(request.user, SignalEvent.Kind.COMPLETE, task=task, minutes=actual)
        messages.success(request, f"Task “{task.title}” completed.")
    else:
        SignalEvent.log(request.user, SignalEvent.Kind.REOPEN, task=task)
        messages.success(request, f"Task “{task.title}” reopened.")
    return redirect("main:index")


@login_required
@require_POST
def delete_task(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    title = task.title
    task.delete()
    messages.success(request, f"Task “{title}” deleted.")
    return redirect("main:index")


@login_required
@require_POST
def clear_completed(request):
    count, _ = Task.objects.filter(owner=request.user, completed=True).delete()
    messages.success(request, f"Cleared {count} completed task(s)." if count else "Nothing to clear.")
    return redirect("main:index")


@login_required
@require_POST
def toggle_sprint(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    task.in_sprint = not task.in_sprint
    task.save(update_fields=["in_sprint", "updated_at"])
    state = "added to sprint" if task.in_sprint else "removed from sprint"
    messages.success(request, f"“{task.title}” {state}.")
    return redirect("main:index")


@login_required
@require_POST
def clear_sprint(request):
    n = Task.objects.filter(owner=request.user, in_sprint=True).update(in_sprint=False)
    messages.success(request, f"Sprint cleared ({n} task(s))." if n else "Sprint already empty.")
    return redirect("main:index")


@login_required
@require_POST
def auto_plan(request):
    """Greedy sprint fill: highest priority first, respecting capacity. Unestimated counts as 1."""
    capacity = request.session.get("sprint_capacity", 21)
    Task.objects.filter(owner=request.user).update(in_sprint=False)
    ordered = list(
        Task.objects.filter(owner=request.user, completed=False).annotate(
            _prank=Case(When(priority="H", then=0), When(priority="M", then=1), When(priority="L", then=2), default=1)
        ).order_by("_prank", "-estimate", "-created_at")
    )
    used, picked = 0, 0
    for t in ordered:
        cost = t.estimate or 1
        if used + cost <= capacity:
            t.in_sprint = True
            t.save(update_fields=["in_sprint", "updated_at"])
            used += cost
            picked += 1
    messages.success(request, f"Auto-planned {picked} task(s) · {used}/{capacity} pts.")
    return redirect("main:index")


@login_required
@require_POST
def snooze_task(request, pk):
    """Push due date out by a Fibonacci step: 1/2/3/5/8/13 days."""
    from datetime import timedelta

    from django.utils import timezone

    task = get_object_or_404(Task, pk=pk, owner=request.user)
    try:
        days = int(request.POST.get("days", 3))
    except (TypeError, ValueError):
        days = 3
    if days not in Task.SNOOZE_STEPS:
        days = 3
    today = timezone.localdate()
    base = max(task.due_date or today, today)
    task.due_date = base + timedelta(days=days)
    task.save(update_fields=["due_date", "updated_at"])
    SignalEvent.log(request.user, SignalEvent.Kind.SNOOZE, task=task, days=days)
    messages.success(request, f"“{task.title}” snoozed +{days}d → {task.due_date} (Fib step).")
    return redirect("main:index")


@login_required
@require_POST
def subtask_add(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    form = SubtaskForm(request.POST)
    if form.is_valid():
        Subtask.objects.create(task=task, title=form.cleaned_data["title"])
        SignalEvent.log(request.user, SignalEvent.Kind.SPLIT, task=task)
        messages.success(request, f"Step added to “{task.title}”.")
    else:
        messages.error(request, "Step needs a title.")
    return redirect(f"{redirect('main:index').url}?open={task.pk}")


@login_required
@require_POST
def subtask_toggle(request, pk):
    from .models import Subtask as _S

    sub = get_object_or_404(_S, pk=pk, task__owner=request.user)
    sub.completed = not sub.completed
    sub.save(update_fields=["completed"])
    return redirect(f"{redirect('main:index').url}?open={sub.task_id}")


@login_required
@require_POST
def subtask_delete(request, pk):
    from .models import Subtask as _S

    sub = get_object_or_404(_S, pk=pk, task__owner=request.user)
    task_id = sub.task_id
    sub.delete()
    messages.success(request, "Step removed.")
    return redirect(f"{redirect('main:index').url}?open={task_id}")


def welcome_view(request):
    """Animated one-look landing: size it, split it, start it."""
    return render(
        request,
        "main/welcome.html",
        {
            "fib_points": Task.FIB_POINTS,
            "estimate_guide": Task.ESTIMATE_GUIDE,
            "focus_presets": Task.FOCUS_PRESETS,
            "task_count": Task.objects.filter(owner=request.user).count() if request.user.is_authenticated else 0,
        },
    )


def guide_view(request):
    """Docs: how to use the app, step by step."""
    return render(
        request,
        "main/guide.html",
        {
            "estimate_guide": Task.ESTIMATE_GUIDE,
            "fib_points": Task.FIB_POINTS,
            "focus_presets": Task.FOCUS_PRESETS,
            "snooze_steps": Task.SNOOZE_STEPS,
        },
    )


@login_required
def focus_view(request):
    minutes_param = request.GET.get("minutes", "13")
    try:
        minutes = int(minutes_param)
    except (TypeError, ValueError):
        minutes = 13
    if minutes not in Task.FOCUS_PRESETS and not (1 <= minutes <= 90):
        minutes = 13
    try:
        task_id = int(request.GET.get("task", 0) or 0)
    except (TypeError, ValueError):
        task_id = 0
    active_task = Task.objects.filter(owner=request.user, pk=task_id, completed=False).first() if task_id else None
    open_tasks = Task.objects.filter(owner=request.user, completed=False).order_by("-in_sprint", "-estimate", "-created_at")[:12]
    today = _today_focus(request.user)
    recent = FocusSession.objects.filter(owner=request.user).select_related("task")[:8]
    ladder = [1, 2, 3, 5]
    return render(
        request,
        "main/focus.html",
        {
            "minutes": minutes,
            "seconds": minutes * 60,
            "presets": Task.FOCUS_PRESETS,
            "ladder": ladder,
            "active_task": active_task,
            "active_task_id": active_task.pk if active_task else 0,
            "open_tasks": open_tasks,
            "today": today,
            "week": _week_focus(request.user),
            "recent": recent,
            "break_minutes": FocusSession.suggested_break(minutes),
        },
    )


@login_required
@require_POST
def focus_log(request):
    try:
        minutes = int(request.POST.get("minutes", 0))
    except (TypeError, ValueError):
        minutes = 0
    if not 1 <= minutes <= 90:
        messages.error(request, "Pick 1–90 minutes for a focus block.")
        return redirect("main:focus")
    task = None
    try:
        task_id = int(request.POST.get("task", 0) or 0)
    except (TypeError, ValueError):
        task_id = 0
    if task_id:
        task = Task.objects.filter(pk=task_id, owner=request.user).first()
    FocusSession.objects.create(owner=request.user, task=task, minutes=minutes)
    SignalEvent.log(request.user, SignalEvent.Kind.FOCUS, task=task, minutes=minutes)
    brk = FocusSession.suggested_break(minutes)
    label = f" on “{task.title}”" if task else ""
    messages.success(request, f"Logged {minutes}m of focus{label}. Take a {brk}m break.")
    return redirect("main:focus")


@login_required
@require_POST
def seed_samples(request):
    """First-run activation: 3 guided sample tasks (only when the user's list is empty)."""
    if Task.objects.filter(owner=request.user).exists():
        messages.info(request, "You already have tasks — samples are for fresh starts.")
        return redirect("main:index")
    from datetime import timedelta

    from django.utils import timezone

    today = timezone.localdate()
    samples = [
        {
            "title": "Bio 101 problem set",
            "course": "Bio 101",
            "priority": "H",
            "estimate": 5,
            "due_date": today + timedelta(days=2),
            "in_sprint": True,
            "notes": "Sample: a 5-pointer. Big enough to need steps.",
            "steps": ["Open the sheet, read Q1 (2 min)", "Solve Q1–Q3", "Check answers"],
        },
        {
            "title": "Essay outline",
            "course": "Eng 201",
            "priority": "M",
            "estimate": 3,
            "due_date": today + timedelta(days=5),
            "in_sprint": True,
            "notes": "Sample: a standard 3. Thesis in one sentence first.",
            "steps": ["Thesis in one sentence"],
        },
        {
            "title": "Tidy desk, plan the week",
            "course": "",
            "priority": "L",
            "estimate": 1,
            "due_date": None,
            "in_sprint": False,
            "notes": "Sample: a 1-point warm-up. Pair it with a 1-min focus.",
            "steps": [],
        },
    ]
    for s in samples:
        steps = s.pop("steps")
        task = Task.objects.create(owner=request.user, **s)
        for title in steps:
            Subtask.objects.create(task=task, title=title)
    messages.success(request, "Loaded 3 sample tasks — point one, split one, focus one.")
    return redirect("main:index")


@login_required
def export_csv(request):
    """Portability: download every task as CSV."""
    import csv

    from django.http import HttpResponse

    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="fibotask.csv"'
    w = csv.writer(resp)
    w.writerow(["id", "title", "course", "priority", "estimate", "in_sprint", "completed", "due_date", "created_at"])
    for t in Task.objects.filter(owner=request.user).order_by("id"):
        w.writerow([t.id, t.title, t.course, t.priority, t.estimate or "", t.in_sprint, t.completed, t.due_date or "", t.created_at.isoformat()])
    return resp


@login_required
@require_POST
def lab_create_task(request):
    """Create a task straight from the Fibonacci Lab estimator."""
    title = (request.POST.get("title") or "").strip()
    try:
        estimate = int(request.POST.get("estimate", 0))
    except (TypeError, ValueError):
        estimate = 0
    if not title:
        messages.error(request, "Give the estimated task a title first.")
        return redirect("main:fibonacci")
    if estimate not in Task.FIB_POINTS:
        messages.error(request, "Pick a Fibonacci estimate (1, 2, 3, 5, 8, 13, 21).")
        return redirect("main:fibonacci")
    Task.objects.create(owner=request.user, title=title[:255], estimate=estimate)
    messages.success(request, f"Estimated “{title}” at {estimate} pts → added to backlog.")
    return redirect("main:index")


def fibonacci_view(request):
    max_terms = getattr(settings, "FIBONACCI_MAX_TERMS", 1000)
    form = FibonacciForm(request.GET or None, max_terms=max_terms)
    series: list[int] = []
    n = None
    stats = None
    if request.GET and form.is_valid():
        n = form.cleaned_data["n"]
        series = fibonacci_series(n)
        if series:
            evens = sum(1 for x in series if x % 2 == 0)
            ratio = series[-1] / series[-2] if len(series) > 2 and series[-2] else None
            stats = {
                "count": len(series),
                "last": series[-1],
                "sum": sum(series),
                "evens": evens,
                "odds": len(series) - evens,
                "ratio": ratio,
                "max": max(series),
            }
        # lightweight session history (last 6 queries)
        hist = request.session.get("fib_history", [])
        if n not in hist:
            hist = [n, *hist][:6]
            request.session["fib_history"] = hist
    elif request.GET:
        messages.error(request, f"Enter a whole number between 1 and {max_terms}.")

    history = request.session.get("fib_history", [])
    # Bar scaling: log-scale so huge terms still render.
    import math

    bars = []
    if series:
        denom = math.log10(max(series[-1], 1) + 1) or 1
        for i, v in enumerate(series[:120]):  # cap rendered bars for DOM sanity
            h = max(4, round(math.log10(v + 1) / denom * 100))
            bars.append({"i": i, "v": v, "h": h, "even": v % 2 == 0})
    truncated = len(series) > len(bars) if series else False

    # Estimator context: which Fib point is selected?
    try:
        sel_points = int(request.GET.get("points", 5))
    except (TypeError, ValueError):
        sel_points = 5
    if sel_points not in Task.FIB_POINTS:
        sel_points = 5

    return render(
        request,
        "main/fibonacci.html",
        {
            "form": form,
            "series": series,
            "bars": bars,
            "truncated": truncated,
            "n": n,
            "stats": stats,
            "history": history,
            "max_terms": max_terms,
            "fib_points": Task.FIB_POINTS,
            "sel_points": sel_points,
            "estimate_guide": Task.ESTIMATE_GUIDE,
        },
    )
