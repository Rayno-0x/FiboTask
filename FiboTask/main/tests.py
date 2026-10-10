from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Task
from .utils import fibonacci_series


class AuthMixin:
    """Every app view requires login: tests run as an isolated user."""

    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(
            username="tester", email="tester@example.com", password="pw123456"
        )
        self.client.force_login(self.user)

    def other_user(self):
        return get_user_model().objects.create_user(
            username="other", email="other@example.com", password="pw123456"
        )


class FibonacciUtilTests(TestCase):
    def test_first_terms(self):
        self.assertEqual(fibonacci_series(0), [])
        self.assertEqual(fibonacci_series(1), [0])
        self.assertEqual(fibonacci_series(10), [0, 1, 1, 2, 3, 5, 8, 13, 21, 34])

    def test_non_positive(self):
        self.assertEqual(fibonacci_series(-5), [])


class TaskViewTests(AuthMixin, TestCase):
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
        task = Task.objects.create(owner=self.user, title="T")
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
        task = Task.objects.create(owner=self.user, title="T")
        self.assertEqual(self.client.get(reverse("main:delete_task", args=[task.pk])).status_code, 405)
        self.assertEqual(Task.objects.count(), 1)
        self.client.post(reverse("main:delete_task", args=[task.pk]))
        self.assertEqual(Task.objects.count(), 0)

    def test_index_paginates(self):
        for i in range(15):
            Task.objects.create(owner=self.user, title=f"T{i}")
        resp = self.client.get(reverse("main:index"))
        self.assertEqual(len(resp.context["page_obj"]), 8)
        resp2 = self.client.get(reverse("main:index") + "?page=2")
        self.assertEqual(len(resp2.context["page_obj"]), 7)

    def test_create_with_priority_and_search_filter(self):
        Task.objects.create(owner=self.user, title="Buy milk", priority="H")
        Task.objects.create(owner=self.user, title="Read book", priority="L", completed=True)
        resp = self.client.get(reverse("main:index") + "?q=milk")
        self.assertContains(resp, "Buy milk")
        self.assertNotContains(resp, "Read book")
        resp = self.client.get(reverse("main:index") + "?status=done")
        self.assertContains(resp, "Read book")
        self.assertNotContains(resp, "Buy milk")

    def test_edit_and_clear_completed(self):
        task = Task.objects.create(owner=self.user, title="Old")
        resp = self.client.post(
            reverse("main:edit_task", args=[task.pk]),
            {"title": "New", "priority": "H", "notes": "hi"},
        )
        self.assertEqual(resp.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.title, "New")
        self.assertEqual(task.priority, "H")
        Task.objects.create(owner=self.user, title="Done one", completed=True)
        self.client.post(reverse("main:clear_completed"))
        self.assertEqual(Task.objects.filter(completed=True).count(), 0)


class FibTasksIntegrationTests(AuthMixin, TestCase):
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
        self.assertRedirects(resp, reverse("main:command"))
        self.assertEqual(Task.objects.count(), 0)

    def test_sprint_toggle_and_filter(self):
        t = Task.objects.create(owner=self.user, title="S", estimate=5)
        self.client.post(reverse("main:toggle_sprint", args=[t.pk]))
        t.refresh_from_db()
        self.assertTrue(t.in_sprint)
        resp = self.client.get(reverse("main:index") + "?status=sprint")
        self.assertContains(resp, "S")

    def test_auto_plan_respects_capacity(self):
        Task.objects.create(owner=self.user, title="Big", estimate=13, priority="H")
        Task.objects.create(owner=self.user, title="Med", estimate=8, priority="M")
        Task.objects.create(owner=self.user, title="Small", estimate=3, priority="M")
        self.client.get(reverse("main:index") + "?capacity=21")
        self.client.post(reverse("main:auto_plan"))
        total = sum((t.estimate or 1) for t in Task.objects.filter(in_sprint=True))
        self.assertLessEqual(total, 21)
        self.assertGreater(total, 0)

    def test_snooze_advances_due_date(self):
        from datetime import date, timedelta

        t = Task.objects.create(owner=self.user, title="Overdue", due_date=date(2020, 1, 1))
        self.client.post(reverse("main:snooze_task", args=[t.pk]), {"days": "5"})
        t.refresh_from_db()
        self.assertGreater(t.due_date, date(2020, 1, 1))
        self.assertEqual((t.due_date - max(date(2020, 1, 1), t.due_date - timedelta(days=5))).days, 5)

    def test_snooze_rejects_non_fib_step(self):
        from datetime import timedelta

        from django.utils import timezone

        t = Task.objects.create(owner=self.user, title="X", due_date=timezone.localdate())
        self.client.post(reverse("main:snooze_task", args=[t.pk]), {"days": "4"})
        t.refresh_from_db()
        # falls back to +3 from today
        self.assertEqual(t.due_date, timezone.localdate() + timedelta(days=3))


class StudentEditionTests(AuthMixin, TestCase):
    def test_subtask_add_toggle_delete(self):
        t = Task.objects.create(owner=self.user, title="Essay", estimate=8)
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
        t = Task.objects.create(owner=self.user, title="Essay")
        self.client.post(reverse("main:subtask_add", args=[t.pk]), {"title": "   "})
        self.assertEqual(t.subtasks.count(), 0)

    def test_focus_page_and_log(self):
        t = Task.objects.create(owner=self.user, title="Study", estimate=5)
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
        Task.objects.create(owner=self.user, title="Zeta problem set", course="Math 101")
        Task.objects.create(owner=self.user, title="Zeta novel draft", course="Eng 201")
        resp = self.client.get(reverse("main:index") + "?course=Math 101")
        self.assertContains(resp, "Zeta problem set")
        self.assertNotContains(resp, "Zeta novel draft")

    def test_needs_split_flag(self):
        big = Task.objects.create(owner=self.user, title="Thesis", estimate=13)
        small = Task.objects.create(owner=self.user, title="Email", estimate=2)
        self.assertTrue(big.needs_split)
        self.assertFalse(small.needs_split)


class CommandLabTests(AuthMixin, TestCase):
    def test_generator_lives_on_command(self):
        resp = self.client.get(reverse("main:command") + "?n=10")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context["series"]), [0, 1, 1, 2, 3, 5, 8, 13, 21, 34])

    def test_invalid_n_shows_error_no_crash(self):
        for bad in ["abc", "-5", "0", "2.5", ""]:
            resp = self.client.get(reverse("main:command") + f"?n={bad}")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(list(resp.context["series"]), [])

    @override_settings(FIBONACCI_MAX_TERMS=20)
    def test_cap_enforced(self):
        resp = self.client.get(reverse("main:command") + "?n=100")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context["series"]), [])

    def test_old_lab_url_redirects_to_command(self):
        resp = self.client.get("/fibonacci/?n=10")
        self.assertRedirects(resp, "/command/")

    def test_command_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("main:command"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("account_login"), resp.url)


class LandingGuideTests(AuthMixin, TestCase):
    def test_welcome_renders_one_look(self):
        self.client.logout()  # landing is for newcomers; members get redirected
        resp = self.client.get(reverse("main:welcome"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Homework,")
        self.assertContains(resp, "Start now")  # anonymous CTA
        self.assertContains(resp, "storyStage")
        self.assertContains(resp, "storyClock")
        self.assertContains(resp, "story-bg")
        self.assertContains(resp, "Sunday night")
        self.client.force_login(self.user)  # member with no history goes to tasks
        resp = self.client.get(reverse("main:welcome"))
        self.assertRedirects(resp, reverse("main:index"))

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

    def test_root_is_landing_and_old_url_redirects(self):
        self.client.logout()
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Homework,")
        resp = self.client.get("/welcome/")
        self.assertRedirects(resp, "/")

    def test_graduated_home_for_active_users(self):
        # New user (<5 sessions) goes to tasks; veteran (5+) to command.
        resp = self.client.get(reverse("main:welcome"))
        self.assertRedirects(resp, reverse("main:index"))
        for _ in range(5):
            self.client.post(reverse("main:focus_log"), {"minutes": "5"})
        resp = self.client.get(reverse("main:welcome"))
        self.assertRedirects(resp, reverse("main:command"))

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
        Task.objects.create(owner=self.user, title="Zeta popup")
        resp = self.client.get(reverse("main:index"))
        self.assertContains(resp, "confirmVeil")
        self.assertContains(resp, "Delete this task?")

    def test_favicon_wired(self):
        resp = self.client.get(reverse("main:index"))
        self.assertContains(resp, "favicon.svg")
        self.assertContains(resp, "apple-touch-icon.png")


class MVPCompletenessTests(AuthMixin, TestCase):
    def test_seed_samples_first_run(self):
        resp = self.client.post(reverse("main:seed_samples"))
        self.assertRedirects(resp, reverse("main:index"))
        self.assertEqual(Task.objects.count(), 3)
        big = Task.objects.get(title="Bio 101 problem set")
        self.assertEqual(big.estimate, 5)
        self.assertEqual(big.subtasks.count(), 3)
        self.assertTrue(big.in_sprint)

    def test_seed_refuses_when_tasks_exist(self):
        Task.objects.create(owner=self.user, title="Mine")
        resp = self.client.post(reverse("main:seed_samples"))
        self.assertRedirects(resp, reverse("main:index"))
        self.assertEqual(Task.objects.count(), 1)

    def test_export_csv(self):
        Task.objects.create(owner=self.user, title="Zeta export", course="Math 101", estimate=3)
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


class AnalyticsTests(AuthMixin, TestCase):
    def test_energy_map_empty_is_neutral(self):
        from .analytics import energy_map

        zones = energy_map(self.user)
        self.assertEqual(len(zones), 5)
        self.assertTrue(all(z["level"] == "steady" or z["level"] == "low" for z in zones))
        self.assertTrue(all(z["minutes"] == 0 for z in zones))

    def test_energy_map_finds_peak_zone(self):
        from .analytics import energy_map
        from .models import FocusSession

        FocusSession.objects.create(owner=self.user, minutes=21)  # current hour's part
        zones = energy_map(self.user)
        self.assertEqual(sum(z["minutes"] for z in zones), 21)
        self.assertIn("peak", [z["level"] for z in zones])

    def test_readiness_new_user_is_charged(self):
        from .analytics import readiness

        r = readiness(self.user)
        self.assertEqual(r["state"], "Charged")
        self.assertLess(r["score"], 35)

    def test_readiness_overload_with_evidence(self):
        from datetime import timedelta

        from django.utils import timezone

        from .analytics import readiness
        from .models import SignalEvent

        today = timezone.localdate()
        Task.objects.create(owner=self.user, title="Huge", estimate=21, due_date=today - timedelta(days=3))
        Task.objects.create(owner=self.user, title="Big", estimate=13, due_date=today - timedelta(days=1))
        Task.objects.create(owner=self.user, title="Med", estimate=8, due_date=today - timedelta(days=1))
        for _ in range(4):
            SignalEvent.objects.create(owner=self.user, kind=SignalEvent.Kind.SNOOZE)
        r = readiness(self.user)
        self.assertEqual(r["state"], "Overloaded")
        self.assertIn("Ease off", r["reason"])

    def test_calibration_message_after_completion(self):
        from .analytics import calibration_summary
        from .models import EstimateRecord

        # Three records so a real bias can emerge (one record is self-referential).
        EstimateRecord.objects.create(owner=self.user, title="Trivial", estimated=2, actual_minutes=4, completed=True)
        EstimateRecord.objects.create(owner=self.user, title="Normal", estimated=3, actual_minutes=6, completed=True)
        EstimateRecord.objects.create(owner=self.user, title="Heavy", estimated=5, actual_minutes=64, completed=True)
        cal = calibration_summary(self.user)
        self.assertEqual(cal["n"], 3)
        self.assertAlmostEqual(cal["rate"], 7.4)
        self.assertIn("size up", cal["message"])

    def test_completion_writes_calibration_record(self):
        from .models import EstimateRecord

        t = Task.objects.create(owner=self.user, title="Calibrated", estimate=5)
        self.client.post(reverse("main:focus_log"), {"minutes": "13", "task": str(t.pk)})
        self.client.post(reverse("main:complete_task", args=[t.pk]))
        rec = EstimateRecord.objects.get(task=t)
        self.assertEqual((rec.owner, rec.estimated, rec.actual_minutes), (self.user, 5, 13))

    def test_at_risk_orders_overdue_first(self):
        from datetime import timedelta

        from django.utils import timezone

        from .analytics import at_risk

        today = timezone.localdate()
        Task.objects.create(owner=self.user, title="Later", estimate=3, due_date=today + timedelta(days=2))
        late = Task.objects.create(owner=self.user, title="Late", estimate=2, due_date=today - timedelta(days=2))
        risks = at_risk(self.user)
        self.assertEqual(risks[0]["task"].pk, late.pk)
        self.assertIn("Overdue", risks[0]["reason"])
        self.assertIn("13 min", risks[0]["action"])

    def test_briefing_starts_with_warmup(self):
        from .analytics import briefing

        Task.objects.create(owner=self.user, title="Epic", estimate=13, priority="H")
        Task.objects.create(owner=self.user, title="Tiny", estimate=1, priority="L")
        queue = briefing(self.user)
        self.assertEqual(queue[0].title, "Tiny")
        self.assertEqual(len(queue), 2)


class CommandViewTests(AuthMixin, TestCase):
    def test_command_renders_all_cards(self):
        Task.objects.create(owner=self.user, title="Cmd task", estimate=5)
        resp = self.client.get(reverse("main:command"))
        self.assertEqual(resp.status_code, 200)
        for needle in ["Command center", "Energy map", "Morning briefing", "At risk", "Estimator", "Sequence explorer"]:
            self.assertContains(resp, needle)
        self.assertIn("readiness", resp.context)
        self.assertIn("briefing", resp.context)

    def test_command_estimator_creates_task(self):
        resp = self.client.post(reverse("main:lab_create_task"), {"title": "From command", "estimate": "3"})
        self.assertRedirects(resp, reverse("main:index"))
        self.assertEqual(Task.objects.get(title="From command").estimate, 3)

    def test_sidebar_gauge_links_command(self):
        resp = self.client.get(reverse("main:index"))
        self.assertContains(resp, reverse("main:command"))

    def test_checkin_flow_every_third_session(self):
        from .models import FocusSession

        for _ in range(2):
            self.client.post(reverse("main:focus_log"), {"minutes": "5"})
        resp = self.client.post(reverse("main:focus_log"), {"minutes": "5"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("checkin=", resp.url)
        session = FocusSession.objects.filter(owner=self.user).latest("id")
        resp = self.client.get(reverse("main:focus") + f"?checkin={session.pk}")
        self.assertContains(resp, "Energy going in")
        resp = self.client.post(
            reverse("main:focus_checkin"),
            {"session": str(session.pk), "energy_in": "2", "energy_out": "4"},
        )
        self.assertRedirects(resp, reverse("main:focus"))
        session.refresh_from_db()
        self.assertEqual((session.energy_in, session.energy_out), (2, 4))

    def test_checkin_rejects_out_of_range(self):
        from .models import FocusSession

        s = FocusSession.objects.create(owner=self.user, minutes=5)
        resp = self.client.post(
            reverse("main:focus_checkin"), {"session": str(s.pk), "energy_in": "9", "energy_out": "0"}
        )
        self.assertEqual(resp.status_code, 302)
        s.refresh_from_db()
        self.assertIsNone(s.energy_out)


class Phase1AuthTests(TestCase):
    def test_anon_redirected_to_login(self):
        for url in ["main:index", "main:focus", "main:export_csv"]:
            resp = self.client.get(reverse(url))
            self.assertEqual(resp.status_code, 302)
            self.assertIn(reverse("account_login"), resp.url)
        resp = self.client.post(reverse("main:index"), {"title": "x"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("account_login"), resp.url)

    def test_signup_creates_user_profile_and_logs_in(self):
        resp = self.client.post(
            reverse("account_signup"),
            {"email": "new@example.com", "username": "newbie", "password1": "s3cure-pass-1", "password2": "s3cure-pass-1"},
        )
        self.assertRedirects(resp, reverse("main:index"))
        user = get_user_model().objects.get(username="newbie")
        self.assertTrue(hasattr(user, "profile"))
        self.assertIsNone(user.profile.organization)

    def test_users_cannot_see_or_touch_each_other(self):
        from .models import Subtask

        mine = Task.objects.create(owner=self._login_as("ana"), title="Ana private")
        theirs = Task.objects.create(owner=self._login_as("bob"), title="Bob private")
        sub = Subtask.objects.create(task=mine, title="Ana step")
        self.client.force_login(theirs.owner)
        resp = self.client.get(reverse("main:index"))
        self.assertContains(resp, "Bob private")
        self.assertNotContains(resp, "Ana private")
        for url in [
            reverse("main:complete_task", args=[mine.pk]),
            reverse("main:delete_task", args=[mine.pk]),
            reverse("main:toggle_sprint", args=[mine.pk]),
            reverse("main:snooze_task", args=[mine.pk]),
            reverse("main:subtask_toggle", args=[sub.pk]),
            reverse("main:subtask_delete", args=[sub.pk]),
        ]:
            self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(self.client.post(reverse("main:edit_task", args=[mine.pk]), {"title": "Hijack"}).status_code, 404)
        mine.refresh_from_db()
        self.assertEqual(mine.title, "Ana private")
        self.assertEqual(Task.objects.filter(owner=theirs.owner).count(), 1)

    def _login_as(self, name):
        user = get_user_model().objects.create_user(username=name, email=f"{name}@x.com", password="pw123456")
        return user

    def test_completion_writes_estimate_record_and_signal(self):
        from .models import EstimateRecord, SignalEvent

        user = self._login_as("cal")
        self.client.force_login(user)
        t = Task.objects.create(owner=user, title="Calibrated", estimate=5)
        self.client.post(reverse("main:focus_log"), {"minutes": "13", "task": str(t.pk)})
        self.client.post(reverse("main:complete_task", args=[t.pk]))
        rec = EstimateRecord.objects.get(task=t)
        self.assertEqual((rec.owner, rec.estimated, rec.actual_minutes), (user, 5, 13))
        kinds = set(SignalEvent.objects.filter(owner=user).values_list("kind", flat=True))
        self.assertTrue({"focus", "complete"} <= kinds)

    def test_snooze_and_split_log_signals(self):
        from .models import SignalEvent

        user = self._login_as("sig")
        self.client.force_login(user)
        t = Task.objects.create(owner=user, title="Sig task")
        self.client.post(reverse("main:snooze_task", args=[t.pk]), {"days": "3"})
        self.client.post(reverse("main:subtask_add", args=[t.pk]), {"title": "First step"})
        kinds = set(SignalEvent.objects.filter(owner=user).values_list("kind", flat=True))
        self.assertTrue({"snooze", "split"} <= kinds)

    def test_seed_and_export_are_per_user(self):
        me = self._login_as("me")
        you = self._login_as("you")
        self.client.force_login(me)
        self.client.post(reverse("main:seed_samples"))
        Task.objects.create(owner=me, title="Me only task")
        self.client.force_login(you)
        self.client.post(reverse("main:seed_samples"))
        self.assertEqual(Task.objects.filter(owner=me).count(), 4)
        self.assertEqual(Task.objects.filter(owner=you).count(), 3)
        resp = self.client.get(reverse("main:export_csv"))
        content = resp.content.decode()
        self.assertIn("Bio 101 problem set", content)
        self.assertNotContains(resp, "Me only task")

    def test_google_button_hidden_without_credentials(self):
        resp = self.client.get(reverse("account_login"))
        self.assertNotContains(resp, "Continue with Google")

    @override_settings(GOOGLE_CLIENT_ID="id", GOOGLE_CLIENT_SECRET="secret")
    def test_google_button_shown_with_credentials(self):
        resp = self.client.get(reverse("account_login"))
        self.assertContains(resp, "Continue with Google")
