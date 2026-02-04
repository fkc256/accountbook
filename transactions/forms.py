"""transactions 앱 폼 — 계좌·거래·영수증·정기거래 입력 폼.

TransactionForm / RecurringTransactionForm 은 user 파라미터를 받아
계좌 드롭다운을 해당 유저의 활성 계좌로만 필터링한다.
AttachmentForm 은 파일 확장자·크기 유효성을 검사한다.
"""

import os

from django import forms
from django.core.exceptions import ValidationError
from .models import Account, Transaction, Attachment, RecurringTransaction

ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".pdf"]
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


class AccountForm(forms.ModelForm):
    """계좌 생성·수정 폼."""

    class Meta:
        model = Account
        fields = ["name", "bank_name", "account_number", "balance", "is_active"]


class TransactionForm(forms.ModelForm):
    """거래 생성·수정 폼. 계좌 드롭다운은 로그인 유저의 활성 계좌만 표시."""

    class Meta:
        model = Transaction
        fields = ["account", "category", "tx_type", "amount", "occurred_at", "merchant", "memo"]
        widgets = {
            "occurred_at": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["account"].queryset = Account.objects.filter(
                user=user, is_active=True
            )


class AttachmentForm(forms.ModelForm):
    """영수증 업로드 폼. 확장자(jpg/png/gif/pdf)와 크기(5MB) 제한."""

    class Meta:
        model = Attachment
        fields = ["file"]

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if f:
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise ValidationError(
                    f"허용되지 않는 파일 형식입니다. ({', '.join(ALLOWED_EXTENSIONS)})"
                )
            if f.size > MAX_FILE_SIZE:
                raise ValidationError("파일 크기는 5MB 이하만 업로드 가능합니다.")
        return f


class RecurringTransactionForm(forms.ModelForm):
    """정기 거래 생성·수정 폼. recurring_day 는 1~31 범위만 허용."""

    class Meta:
        model = RecurringTransaction
        fields = [
            "account", "category", "tx_type", "amount",
            "recurring_day", "merchant", "memo",
            "start_date", "end_date", "is_active",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["account"].queryset = Account.objects.filter(
                user=user, is_active=True
            )

    def clean_recurring_day(self):
        day = self.cleaned_data.get("recurring_day")
        if day is not None and not (1 <= day <= 31):
            raise ValidationError("실행일은 1~31 사이여야 합니다.")
        return day
