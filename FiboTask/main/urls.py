from django.urls import path

from . import views

app_name = "main"

urlpatterns = [
    path("", views.index, name="index"),
    path("complete/<int:pk>/", views.complete_task, name="complete_task"),
    path("delete/<int:pk>/", views.delete_task, name="delete_task"),
    path("fibonacci/", views.fibonacci_view, name="fibonacci"),
]
