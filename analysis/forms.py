"""analysis 앱 폼 — 재무 목표 입력 폼."""

from django import forms
from transactions.models import Goal


class GoalForm(forms.ModelForm):
    """목표 저축·월 소비 한도 설정 폼."""

    class Meta:
        model = Goal
        fields = ["target_saving", "monthly_spending_limit"]
