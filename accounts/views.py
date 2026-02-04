"""accounts 앱 뷰 — 회원가입·로그인·로그아웃 처리.

Django 내장 User 모델을 사용하며, 별도의 프로필 모델 없이
기본 인증(username + password) 방식으로 동작한다.
"""

from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from .forms import SignupForm


def signup_view(request):
    """회원가입 뷰. 가입 성공 시 자동 로그인 후 계좌 목록으로 이동."""
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("account_list")
    else:
        form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form})


def login_view(request):
    """로그인 뷰. ?next= 파라미터가 있으면 로그인 후 해당 URL로 리다이렉트."""
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get("next", "account_list")
            return redirect(next_url)
        else:
            return render(request, "accounts/login.html", {
                "error": "아이디 또는 비밀번호가 올바르지 않습니다.",
            })
    return render(request, "accounts/login.html")


def logout_view(request):
    """로그아웃 후 로그인 페이지로 리다이렉트."""
    logout(request)
    return redirect("login")
