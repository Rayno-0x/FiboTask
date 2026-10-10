"""Template context shared across the app."""

from django.conf import settings


def auth_extras(request):
    return {
        "google_enabled": bool(
            getattr(settings, "GOOGLE_CLIENT_ID", "") and getattr(settings, "GOOGLE_CLIENT_SECRET", "")
        ),
    }
