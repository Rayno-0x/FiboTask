"""Phase 2 predictive engine — transparent arithmetic, no black boxes.

Every function returns plain data plus a human-readable reason string.
Nothing here invents precision: sparse data yields neutral bands, never
fake confidence.
"""

from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

DAY_PARTS = (
    ("night", "Night", 0, 5),
    ("morning", "Morning", 5, 11),
    ("midday", "Midday", 11, 15),
    ("afternoon", "Afternoon", 15, 19),
    ("evening", "Evening", 19, 24),
)

# Starting assumption until personal data exists (documented, not hidden).
DEFAULT_WEEKLY_VELOCITY = 5  # pts/week
DEFAULT_MIN_PER_POINT = 20  # minutes per point


def _part_of(hour: int) -> str:
    for key, _label, start, end in DAY_PARTS:
        if start <= hour < end:
            return key
    return "night"


def energy_map(user):
    """Passive heatmap: where does this student's focus actually live?

    Blends logged minutes per day-part with sampled energy check-ins.
    Returns zones ordered night → evening with a peak/steady/low level.
    """
    from .models import FocusSession

    sessions = FocusSession.objects.filter(owner=user).order_by("created_at")
    parts = {key: {"key": key, "label": label, "minutes": 0, "sessions": 0, "energy": []} for key, label, _s, _e in DAY_PARTS}
    for s in sessions:
        hour = s.created_at.astimezone(timezone.get_current_timezone()).hour if timezone.is_aware(s.created_at) else s.created_at.hour
        p = parts[_part_of(hour)]
        p["minutes"] += s.minutes
        p["sessions"] += 1
        if s.energy_out:
            p["energy"].append(s.energy_out)
    peak = max((p["minutes"] for p in parts.values()), default=0)
    zones = []
    for key, _label, _s, _e in DAY_PARTS:
        p = parts[key]
        avg_energy = round(sum(p["energy"]) / len(p["energy"]), 1) if p["energy"] else None
        share = (p["minutes"] / peak) if peak else 0
        if avg_energy is not None:
            level = "peak" if avg_energy >= 4 else "low" if avg_energy <= 2 else "steady"
        else:
            level = "peak" if share >= 0.6 else "low" if share <= 0.15 and p["sessions"] else "steady"
        zones.append(
            {
                "key": key,
                "label": p["label"],
                "minutes": p["minutes"],
                "sessions": p["sessions"],
                "energy": avg_energy,
                "share": round(share * 100),
                "level": level,
            }
        )
    return zones


def readiness(user):
    """Burnout gauge: Charged / Stretched / Overloaded + top reason.

    Weighted, explainable, capped inputs. New users default to Charged —
    the engine accuses only with evidence.
    """
    from .models import FocusSession, SignalEvent, Task

    today = timezone.localdate()
    open_tasks = Task.objects.filter(owner=user, completed=False)
    open_pts = sum(t.estimate or 1 for t in open_tasks)
    overdue = open_tasks.filter(due_date__lt=today).count()
    four_weeks_ago = today - timedelta(days=28)
    shipped_4w = (
        Task.objects.filter(owner=user, completed=True, updated_at__date__gte=four_weeks_ago).aggregate(
            v=Sum("estimate")
        )["v"]
        or 0
    )
    weekly_velocity = shipped_4w / 4 if shipped_4w else DEFAULT_WEEKLY_VELOCITY
    weeks_of_work = open_pts / weekly_velocity if weekly_velocity else 0
    load = min(weeks_of_work / 3 * 100, 100)  # 3+ weeks queued = max pressure
    overdue_score = min(overdue / 5 * 100, 100)
    week_ago = today - timedelta(days=7)
    snoozes = SignalEvent.objects.filter(owner=user, kind=SignalEvent.Kind.SNOOZE, created_at__date__gte=week_ago).count()
    snooze_score = min(snoozes / 4 * 100, 100)
    sessions = list(FocusSession.objects.filter(owner=user).order_by("-created_at")[:30])
    late = sum(1 for s in sessions if (s.created_at.hour >= 23 or s.created_at.hour < 5))
    late_share = (late / len(sessions) * 100) if sessions else 0
    recent = [s.minutes for s in sessions[:7]]
    older = [s.minutes for s in sessions[7:14]]
    shrink = 0
    if recent and older and sum(older):
        shrink = max(0, (sum(older) / len(older) - sum(recent) / len(recent)) / (sum(older) / len(older)) * 100)
    score = round(load * 0.40 + overdue_score * 0.20 + snooze_score * 0.15 + late_share * 0.15 + min(shrink, 100) * 0.10)
    factors = [
        ("load", load, f"{open_pts} pts open ≈ {weeks_of_work:.1f} weeks at your pace"),
        ("overdue", overdue_score, f"{overdue} overdue"),
        ("snooze", snooze_score, f"{snoozes} snoozes this week"),
        ("late", late_share, f"{round(late_share)}% of recent sessions after 11pm"),
        ("shrink", min(shrink, 100), "sessions getting shorter"),
    ]
    top = max(factors, key=lambda f: f[1])
    if score < 35:
        state, reason = "Charged", "Load looks sustainable. Good week to take on more."
    elif score < 65:
        state, reason = "Stretched", f"Watch: {top[2]}."
    else:
        state, reason = "Overloaded", f"Ease off: {top[2]}."
    return {"score": score, "state": state, "reason": reason, "factors": {k: round(v) for k, v, _ in factors}}


def calibration_summary(user):
    """Personal min-per-point + biggest sizing bias, in plain words."""
    from .models import EstimateRecord

    records = list(EstimateRecord.objects.filter(owner=user, completed=True, estimated__isnull=False))
    if not records:
        return {"rate": None, "n": 0, "message": "Complete estimated tasks to calibrate."}
    total_pts = sum(r.estimated for r in records if r.estimated) or 0
    total_min = sum(r.actual_minutes for r in records)
    rate = round(total_min / total_pts, 1) if total_pts else None
    message = None
    if rate:
        worst = None
        for r in records:
            if not r.estimated:
                continue
            implied = r.actual_minutes / rate if rate else 0
            gap = abs(implied - r.estimated)
            if worst is None or gap > worst[0]:
                worst = (gap, r, implied)
        if worst and worst[0] >= 2:
            _gap, rec, implied = worst
            direction = "up" if implied > (rec.estimated or 0) else "down"
            message = f"“{rec.title[:40]}” rated {rec.estimated}, ran like {round(implied)} — size {direction} next time."
        else:
            message = f"Your estimates land well. A point costs you ~{rate} min."
    return {"rate": rate, "n": len(records), "message": message}


def at_risk(user, limit=3):
    """Top risks, each paired with one action. Deterministic order."""
    from .models import Task

    today = timezone.localdate()
    picked, seen = [], set()

    def take(qs):
        for t in qs:
            if t.pk not in seen and len(picked) < limit:
                seen.add(t.pk)
                picked.append(t)

    take(Task.objects.filter(owner=user, completed=False, due_date__lt=today).order_by("due_date"))
    take(
        Task.objects.filter(owner=user, completed=False, due_date__gte=today, due_date__lte=today + timedelta(days=3))
        .exclude(pk__in=seen)
        .order_by("-estimate", "due_date")
    )
    take(Task.objects.filter(owner=user, completed=False).exclude(pk__in=seen).order_by("-estimate", "-created_at"))
    risks = []
    for t in picked[:limit]:
        if t.is_overdue:
            action = "Split it first" if t.needs_split else "Focus 13 min today"
            reason = f"Overdue since {t.due_date}"
        elif t.due_date:
            action = "Split it first" if t.needs_split else "Start with a 5-min draft"
            reason = f"Due {t.due_date}"
        else:
            action = "Split it into steps" if t.needs_split else "Add it to your sprint"
            reason = f"{t.estimate or 'Unestimated'} pts, no date"
        risks.append({"task": t, "reason": reason, "action": action})
    return risks


def briefing(user, limit=5):
    """Tomorrow-morning queue: one warm-up, then sprint work by priority."""
    from .models import Task

    open_tasks = list(Task.objects.filter(owner=user, completed=False).prefetch_related("subtasks"))
    if not open_tasks:
        return []
    rank = {"H": 0, "M": 1, "L": 2}
    warm = min(open_tasks, key=lambda t: (t.estimate or 1, t.created_at))
    queue, seen = [warm], {warm.pk}
    sprint = sorted(
        [t for t in open_tasks if t.in_sprint and t.pk not in seen],
        key=lambda t: (rank.get(t.priority, 1), -(t.estimate or 0)),
    )
    rest = sorted(
        [t for t in open_tasks if t.pk not in seen and t not in sprint],
        key=lambda t: (rank.get(t.priority, 1), -(t.estimate or 0)),
    )
    for t in sprint + rest:
        if len(queue) >= limit:
            break
        queue.append(t)
    return queue[:limit]
