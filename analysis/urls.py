"""analysis 앱 URL 설정 — InMoney 분석·목표·GPT 분석 엔드포인트."""

from django.urls import path
from . import views

urlpatterns = [
    path("", views.inmoney_view, name="inmoney"),                   # 재무 건강 분석 페이지
    path("goal/", views.goal_update_view, name="goal_update"),      # 목표 설정/수정
    path("gpt-analysis/", views.gpt_analysis_view, name="gpt_analysis"),  # GPT 분석 API (POST)
]
