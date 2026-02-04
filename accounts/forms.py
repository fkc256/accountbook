"""accounts 앱 폼 — 회원가입 폼 정의."""

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class SignupForm(UserCreationForm):
    """Django 기본 UserCreationForm 을 상속한 회원가입 폼.

    username, password1(비밀번호), password2(비밀번호 확인) 세 필드만 사용한다.
    """

    class Meta:
        model = User
        fields = ["username", "password1", "password2"]
