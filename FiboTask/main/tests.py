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
        self.assertEqual(len(resp.context["page_obj"]), 10)
        resp2 = self.client.get(reverse("main:index") + "?page=2")
        self.assertEqual(len(resp2.context["page_obj"]), 5)


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
