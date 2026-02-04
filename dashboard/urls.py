"""dashboard 앱 URL 설정."""

from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),      # /dashboard/
    path("home/", views.home_view, name="home"),           # /dashboard/home/
]
