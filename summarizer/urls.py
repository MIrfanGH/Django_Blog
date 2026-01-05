# summarizer/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("<int:post_id>/", views.summarize_post, name="summarize_post"),
]
