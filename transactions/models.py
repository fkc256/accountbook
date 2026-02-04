"""transactions 앱 모델 — 가계부의 핵심 데이터 스키마.

모델 구성:
- Account            : 은행 계좌 (잔액을 직접 추적)
- Category           : 거래 카테고리 (수입/지출/공통, 만족 소비 여부 플래그)
- Transaction        : 개별 거래 (입금/출금, 거래 후 잔액 스냅샷 보관)
- Attachment         : 거래에 1:1 매핑되는 영수증 첨부파일
- Goal               : 유저별 월 목표 저축·소비 한도 (1:1)
- RecurringTransaction : 매월 자동 실행되는 정기 거래 템플릿
"""

from django.conf import settings
from django.db import models


class Account(models.Model):
    """은행/금융기관 계좌.

    잔액(balance)은 거래 생성·수정·삭제 시 views.py 의
    _apply_balance / _reverse_balance 헬퍼로 원자적으로 갱신된다.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="accounts",
    )
    name = models.CharField("계좌 별칭", max_length=50)
    bank_name = models.CharField("은행/기관명", max_length=50)
    account_number = models.CharField("계좌번호", max_length=30)
    balance = models.IntegerField("잔액", default=0)
    is_active = models.BooleanField("활성 여부", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def masked_account_number(self):
        """계좌번호를 '110-****-9012' 형식으로 마스킹하여 반환."""
        num = self.account_number
        if len(num) <= 4:
            return "****"
        return num[:3] + "-" + "*" * (len(num) - 7) + "-" + num[-4:]

    def __str__(self):
        return f"{self.name} ({self.bank_name})"

    class Meta:
        ordering = ["-created_at"]


class Category(models.Model):
    """거래 카테고리.

    cat_type 으로 수입/지출/공통을 구분하고,
    is_satisfaction 플래그가 True 인 카테고리는 InMoney 의
    '만족 소비' 분석 대상에 포함된다.
    """

    INCOME = "IN"
    EXPENSE = "OUT"
    COMMON = "COMMON"
    TYPE_CHOICES = [
        (INCOME, "수입"),
        (EXPENSE, "지출"),
        (COMMON, "공통"),
    ]

    name = models.CharField("카테고리명", max_length=50)
    cat_type = models.CharField(
        "유형", max_length=6, choices=TYPE_CHOICES, default=COMMON
    )
    is_satisfaction = models.BooleanField("만족 소비 여부", default=False)

    def __str__(self):
        return f"{self.name} ({self.get_cat_type_display()})"

    class Meta:
        verbose_name_plural = "Categories"


class Transaction(models.Model):
    """개별 입출금 거래.

    balance_after 는 거래 생성 시점의 계좌 잔액 스냅샷이다.
    occurred_at 기준 내림차순으로 정렬되며, 인덱스가 설정되어 있다.
    """

    IN = "IN"
    OUT = "OUT"
    TX_TYPE_CHOICES = [
        (IN, "입금"),
        (OUT, "출금"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    tx_type = models.CharField(
        "입출금 구분", max_length=3, choices=TX_TYPE_CHOICES
    )
    amount = models.IntegerField("금액")
    balance_after = models.IntegerField("거래 후 잔액", null=True, blank=True)
    occurred_at = models.DateField("거래일")
    merchant = models.CharField("가맹점/거래처", max_length=100, blank=True)
    memo = models.CharField("메모", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_tx_type_display()} {self.amount:,}"

    class Meta:
        ordering = ["-occurred_at", "-created_at"]
        indexes = [
            models.Index(fields=["-occurred_at"]),
        ]


class Attachment(models.Model):
    """거래에 첨부된 영수증 파일 (1:1 관계).

    파일은 'receipts/YYYY/MM/' 경로에 저장된다.
    original_name 에 업로드 시 원본 파일명을 보관한다.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    transaction = models.OneToOneField(
        Transaction,
        on_delete=models.CASCADE,
        related_name="attachment",
    )
    file = models.FileField("영수증 파일", upload_to="receipts/%Y/%m/")
    original_name = models.CharField("원본 파일명", max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"영수증: {self.original_name or self.file.name}"


class Goal(models.Model):
    """유저별 재무 목표 (1:1). [추가 엔티티 — 기본 5개 외 확장]

    target_saving          — 목표 저축 금액 (기간 전체)
    monthly_spending_limit  — 월 소비 한도
    InMoney 페이지에서 달성률 계산에 사용된다.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="goal",
    )
    target_saving = models.IntegerField("목표 저축 금액", default=0)
    monthly_spending_limit = models.IntegerField("월 목표 소비 금액", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}의 목표"


class RecurringTransaction(models.Model):
    """매월 반복되는 정기 거래 템플릿. [추가 엔티티 — 기본 5개 외 확장]

    recurring_day 에 지정된 날짜에 management command(process_recurring)가
    실제 Transaction 을 자동 생성한다.
    end_date 가 지나면 is_active 가 False 로 전환된다.
    """

    TX_TYPE_CHOICES = Transaction.TX_TYPE_CHOICES

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recurring_transactions",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="recurring_transactions",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurring_transactions",
    )
    tx_type = models.CharField("입출금 구분", max_length=3, choices=TX_TYPE_CHOICES)
    amount = models.IntegerField("금액")
    recurring_day = models.IntegerField("실행일 (매달)")
    merchant = models.CharField("가맹점/거래처", max_length=100, blank=True)
    memo = models.CharField("메모", max_length=255, blank=True)
    start_date = models.DateField("시작일")
    end_date = models.DateField("종료일", null=True, blank=True)
    is_active = models.BooleanField("활성 여부", default=True)
    last_executed = models.DateField("마지막 실행일", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[정기] {self.get_tx_type_display()} {self.amount:,} (매달 {self.recurring_day}일)"

    class Meta:
        ordering = ["recurring_day"]
