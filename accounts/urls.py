"""accounts 앱 URL 설정 — 인증 관련 경로."""

from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),       # 로그인
    path("logout/", views.logout_view, name="logout"),     # 로그아웃
    path("signup/", views.signup_view, name="signup"),     # 회원가입
]
