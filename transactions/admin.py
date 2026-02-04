"""transactions 앱 Django Admin 설정.

모든 주요 모델(Account, Category, Transaction, Attachment,
RecurringTransaction, Goal)을 관리자 페이지에 등록한다.
"""

from django.contrib import admin
from .models import Account, Category, Transaction, Attachment, RecurringTransaction, Goal


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """계좌 관리 — 마스킹된 계좌번호로 표시."""
    list_display = ["name", "bank_name", "masked_account_number", "is_active", "user"]
    list_filter = ["is_active", "bank_name"]
    search_fields = ["name", "bank_name"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """카테고리 관리 — 유형(수입/지출)과 만족 소비 여부로 필터."""
    list_display = ["name", "cat_type", "is_satisfaction"]
    list_filter = ["cat_type", "is_satisfaction"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """거래 관리 — 입출금·날짜·카테고리 필터, 메모·가맹점 검색."""
    list_display = ["user", "account", "tx_type", "amount", "balance_after", "category", "occurred_at"]
    list_filter = ["tx_type", "occurred_at", "category"]
    search_fields = ["memo", "merchant"]


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ["transaction", "original_name", "uploaded_at"]


@admin.register(RecurringTransaction)
class RecurringTransactionAdmin(admin.ModelAdmin):
    """정기 거래 관리."""
    list_display = [
        "user", "tx_type", "amount", "account",
        "recurring_day", "is_active", "last_executed",
    ]
    list_filter = ["is_active", "tx_type"]
    search_fields = ["memo", "merchant"]


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    """재무 목표 관리."""
    list_display = ["user", "target_saving", "monthly_spending_limit"]
