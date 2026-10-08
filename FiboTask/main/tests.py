from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Task
from .utils import fibonacci_series


class FibonacciUtilTests(TestCase):
    def test_first_terms(self):
        self.assertEqual(fibonacci_series(0), [])
        self.assertEqual(fibonacci_series(1), [0])
        self.assertEqual(fibonacci_series(10), [0, 1, 1, 2, 3, 5, 8, 13, 21, 34])

    def test_non_positive(self):
        self.assertEqual(fibonacci_series(-5), [])


class TaskViewTests(TestCase):
    def test_create_task_valid(self):
        resp = self.client.post(reverse("main:index"), {"title": "  Buy milk  "})
        self.assertRedirects(resp, reverse("main:index"))
        self.assertEqual(Task.objects.count(), 1)
        self.assertEqual(Task.objects.get().title, "Buy milk")

    def test_create_task_empty_rejected(self):
        resp = self.client.post(reverse("main:index"), {"title": "   "})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Task.objects.count(), 0)

    def test_complete_requires_post_and_toggles(self):
        task = Task.objects.create(title="T")
        resp = self.client.get(reverse("main:complete_task", args=[task.pk]))
        self.assertEqual(resp.status_code, 405)  # GET must not mutate
        task.refresh_from_db()
        self.assertFalse(task.completed)

        self.client.post(reverse("main:complete_task", args=[task.pk]))
        task.refresh_from_db()
        self.assertTrue(task.completed)
        # toggle back (Undo)
        self.client.post(reverse("main:complete_task", args=[task.pk]))
        task.refresh_from_db()
        self.assertFalse(task.completed)

    def test_delete_requires_post(self):
        task = Task.objects.create(title="T")
        self.assertEqual(self.client.get(reverse("main:delete_task", args=[task.pk])).status_code, 405)
        self.assertEqual(Task.objects.count(), 1)
        self.client.post(reverse("main:delete_task", args=[task.pk]))
        self.assertEqual(Task.objects.count(), 0)

    def test_index_paginates(self):
        for i in range(15):
            Task.objects.create(title=f"T{i}")
        resp = self.client.get(reverse("main:index"))
        self.assertEqual(len(resp.context["page_obj"]), 8)
        resp2 = self.client.get(reverse("main:index") + "?page=2")
        self.assertEqual(len(resp2.context["page_obj"]), 7)

    def test_create_with_priority_and_search_filter(self):
        Task.objects.create(title="Buy milk", priority="H")
        Task.objects.create(title="Read book", priority="L", completed=True)
        resp = self.client.get(reverse("main:index") + "?q=milk")
        self.assertContains(resp, "Buy milk")
        self.assertNotContains(resp, "Read book")
        resp = self.client.get(reverse("main:index") + "?status=done")
        self.assertContains(resp, "Read book")
        self.assertNotContains(resp, "Buy milk")

    def test_edit_and_clear_completed(self):
        task = Task.objects.create(title="Old")
        resp = self.client.post(
            reverse("main:edit_task", args=[task.pk]),
            {"title": "New", "priority": "H", "notes": "hi"},
        )
        self.assertEqual(resp.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.title, "New")
        self.assertEqual(task.priority, "H")
        Task.objects.create(title="Done one", completed=True)
        self.client.post(reverse("main:clear_completed"))
        self.assertEqual(Task.objects.filter(completed=True).count(), 0)


class FibTasksIntegrationTests(TestCase):
    def test_create_with_estimate(self):
        resp = self.client.post(
            reverse("main:index"), {"title": "API work", "estimate": "8", "priority": "H"}
        )
        self.assertRedirects(resp, reverse("main:index"))
        self.assertEqual(Task.objects.get().estimate, 8)

    def test_lab_create_task(self):
        resp = self.client.post(
            reverse("main:lab_create_task"), {"title": "Sized in lab", "estimate": "5"}
        )
        self.assertRedirects(resp, reverse("main:index"))
        t = Task.objects.get(title="Sized in lab")
        self.assertEqual(t.estimate, 5)

    def test_lab_create_rejects_non_fib(self):
        resp = self.client.post(
            reverse("main:lab_create_task"), {"title": "Bad", "estimate": "7"}
        )
        self.assertRedirects(resp, reverse("main:fibonacci"))
        self.assertEqual(Task.objects.count(), 0)

    def test_sprint_toggle_and_filter(self):
        t = Task.objects.create(title="S", estimate=5)
        self.client.post(reverse("main:toggle_sprint", args=[t.pk]))
        t.refresh_from_db()
        self.assertTrue(t.in_sprint)
        resp = self.client.get(reverse("main:index") + "?status=sprint")
        self.assertContains(resp, "S")

    def test_auto_plan_respects_capacity(self):
        Task.objects.create(title="Big", estimate=13, priority="H")
        Task.objects.create(title="Med", estimate=8, priority="M")
        Task.objects.create(title="Small", estimate=3, priority="M")
        self.client.get(reverse("main:index") + "?capacity=21")
        self.client.post(reverse("main:auto_plan"))
        total = sum((t.estimate or 1) for t in Task.objects.filter(in_sprint=True))
        self.assertLessEqual(total, 21)
        self.assertGreater(total, 0)

    def test_snooze_advances_due_date(self):
        from datetime import date, timedelta

        t = Task.objects.create(title="Overdue", due_date=date(2020, 1, 1))
        self.client.post(reverse("main:snooze_task", args=[t.pk]), {"days": "5"})
        t.refresh_from_db()
        self.assertGreater(t.due_date, date(2020, 1, 1))
        self.assertEqual((t.due_date - max(date(2020, 1, 1), t.due_date - timedelta(days=5))).days, 5)

    def test_snooze_rejects_non_fib_step(self):
        from datetime import timedelta

        from django.utils import timezone

        t = Task.objects.create(title="X", due_date=timezone.localdate())
        self.client.post(reverse("main:snooze_task", args=[t.pk]), {"days": "4"})
        t.refresh_from_db()
        # falls back to +3 from today
        self.assertEqual(t.due_date, timezone.localdate() + timedelta(days=3))


class StudentEditionTests(TestCase):
    def test_subtask_add_toggle_delete(self):
        t = Task.objects.create(title="Essay", estimate=8)
        resp = self.client.post(reverse("main:subtask_add", args=[t.pk]), {"title": "Outline"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(t.subtasks.count(), 1)
        s = t.subtasks.get()
        self.client.post(reverse("main:subtask_toggle", args=[s.pk]))
        s.refresh_from_db()
        self.assertTrue(s.completed)
        self.client.post(reverse("main:subtask_delete", args=[s.pk]))
        self.assertEqual(t.subtasks.count(), 0)

    def test_subtask_requires_title(self):
        t = Task.objects.create(title="Essay")
        self.client.post(reverse("main:subtask_add", args=[t.pk]), {"title": "   "})
        self.assertEqual(t.subtasks.count(), 0)

    def test_focus_page_and_log(self):
        t = Task.objects.create(title="Study", estimate=5)
        resp = self.client.get(reverse("main:focus") + f"?minutes=5&task={t.pk}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["minutes"], 5)
        resp = self.client.post(reverse("main:focus_log"), {"minutes": "5", "task": str(t.pk)})
        self.assertRedirects(resp, reverse("main:focus"))
        self.assertEqual(t.focus_sessions.count(), 1)

    def test_focus_log_rejects_bad_minutes(self):
        resp = self.client.post(reverse("main:focus_log"), {"minutes": "0"})
        self.assertRedirects(resp, reverse("main:focus"))
        from .models import FocusSession

        self.assertEqual(FocusSession.objects.count(), 0)

    def test_course_filter_and_search(self):
        Task.objects.create(title="Zeta problem set", course="Math 101")
        Task.objects.create(title="Zeta novel draft", course="Eng 201")
        resp = self.client.get(reverse("main:index") + "?course=Math 101")
        self.assertContains(resp, "Zeta problem set")
        self.assertNotContains(resp, "Zeta novel draft")

    def test_needs_split_flag(self):
        big = Task.objects.create(title="Thesis", estimate=13)
        small = Task.objects.create(title="Email", estimate=2)
        self.assertTrue(big.needs_split)
        self.assertFalse(small.needs_split)


class FibonacciViewTests(TestCase):
    def test_valid_n(self):
        resp = self.client.get(reverse("main:fibonacci") + "?n=10")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context["series"]), [0, 1, 1, 2, 3, 5, 8, 13, 21, 34])

    def test_invalid_n_shows_error_no_crash(self):
        for bad in ["abc", "-5", "0", "2.5", ""]:
            resp = self.client.get(reverse("main:fibonacci") + f"?n={bad}")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(list(resp.context["series"]), [])

    @override_settings(FIBONACCI_MAX_TERMS=20)
    def test_cap_enforced(self):
        resp = self.client.get(reverse("main:fibonacci") + "?n=100")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context["series"]), [])


class LandingGuideTests(TestCase):
    def test_welcome_renders_one_look(self):
        resp = self.client.get(reverse("main:welcome"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Homework,")
        self.assertContains(resp, "Start now")
        self.assertContains(resp, "storyStage")
        self.assertContains(resp, "storyClock")
        self.assertContains(resp, "story-bg")
        self.assertContains(resp, "Sunday night")

    def test_guide_renders_docs(self):
        resp = self.client.get(reverse("main:guide"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Rule of 8")
        self.assertContains(resp, "Estimate with points")
        self.assertContains(resp, "FAQ")

    def test_nav_links_pages_together(self):
        resp = self.client.get(reverse("main:index"))
        self.assertContains(resp, reverse("main:guide"))
        self.assertContains(resp, reverse("main:focus"))

    def test_prod_refuses_dev_secret_key(self):
        """Booting with DEBUG off and no SECRET_KEY must fail loudly."""
        import os
        import subprocess
        import sys

        from django.conf import settings as dj_settings

        env = {**os.environ, "DEBUG": "False"}
        env.pop("SECRET_KEY", None)
        r = subprocess.run(
            [sys.executable, "manage.py", "check"],
            capture_output=True,
            text=True,
            cwd=str(dj_settings.BASE_DIR),
            env=env,
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("SECRET_KEY", r.stderr)

    def test_confirm_popup_markup_present(self):
        Task.objects.create(title="Zeta popup")
        resp = self.client.get(reverse("main:index"))
        self.assertContains(resp, "confirmVeil")
        self.assertContains(resp, "Delete this task?")

    def test_favicon_wired(self):
        resp = self.client.get(reverse("main:index"))
        self.assertContains(resp, "favicon.svg")
        self.assertContains(resp, "apple-touch-icon.png")


class MVPCompletenessTests(TestCase):
    def test_seed_samples_first_run(self):
        resp = self.client.post(reverse("main:seed_samples"))
        self.assertRedirects(resp, reverse("main:index"))
        self.assertEqual(Task.objects.count(), 3)
        big = Task.objects.get(title="Bio 101 problem set")
        self.assertEqual(big.estimate, 5)
        self.assertEqual(big.subtasks.count(), 3)
        self.assertTrue(big.in_sprint)

    def test_seed_refuses_when_tasks_exist(self):
        Task.objects.create(title="Mine")
        resp = self.client.post(reverse("main:seed_samples"))
        self.assertRedirects(resp, reverse("main:index"))
        self.assertEqual(Task.objects.count(), 1)

    def test_export_csv(self):
        Task.objects.create(title="Zeta export", course="Math 101", estimate=3)
        resp = self.client.get(reverse("main:export_csv"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        content = resp.content.decode()
        self.assertIn("title,course,priority,estimate", content)
        self.assertIn("Zeta export", content)

    def test_focus_week_stats_present(self):
        resp = self.client.get(reverse("main:focus"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("week", resp.context)
        self.assertIn("This week", resp.content.decode())
