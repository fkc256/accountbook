"""정기 거래 자동 실행 커맨드.

매일 cron 등으로 실행하면 오늘 날짜와 recurring_day 가 일치하는
정기 거래를 찾아 실제 Transaction 을 생성하고 계좌 잔액을 갱신한다.

사용법: python manage.py process_recurring

처리 로직:
  1. 종료일이 지난 정기 거래 → is_active = False 로 비활성화
  2. 이번 달 이미 실행된 정기 거래 → 스킵
  3. 그 외 → Transaction 생성 + 잔액 갱신 + last_executed 갱신
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db.models import F

from transactions.models import RecurringTransaction, Transaction, Account


class Command(BaseCommand):
    help = "오늘 날짜와 일치하는 정기 거래를 실행하여 Transaction을 자동 생성합니다."

    def handle(self, *args, **options):
        today = date.today()
        day = today.day

        recurring_qs = RecurringTransaction.objects.filter(
            is_active=True,
            recurring_day__lte=day,  # 오늘 이전 날짜도 포함 (놓친 정기거래 처리)
            start_date__lte=today,
        ).select_related("account", "user")

        created = 0
        skipped = 0

        for rec in recurring_qs:
            # 종료일 체크
            if rec.end_date and rec.end_date < today:
                rec.is_active = False
                rec.save(update_fields=["is_active"])
                skipped += 1
                continue

            # 이번 달 이미 실행했는지 체크
            if rec.last_executed and (
                rec.last_executed.year == today.year
                and rec.last_executed.month == today.month
            ):
                skipped += 1
                continue

            # Transaction 생성
            Transaction.objects.create(
                user=rec.user,
                account=rec.account,
                category=rec.category,
                tx_type=rec.tx_type,
                amount=rec.amount,
                occurred_at=today,
                merchant=rec.merchant,
                memo=f"[정기] {rec.memo}" if rec.memo else "[정기 거래]",
            )

            # 잔액 업데이트
            if rec.tx_type == "IN":
                Account.objects.filter(pk=rec.account_id).update(
                    balance=F("balance") + rec.amount
                )
            else:
                Account.objects.filter(pk=rec.account_id).update(
                    balance=F("balance") - rec.amount
                )

            # 마지막 실행일 갱신
            rec.last_executed = today
            rec.save(update_fields=["last_executed"])
            created += 1

        self.stdout.write(
            self.style.SUCCESS(f"완료: {created}건 생성, {skipped}건 스킵")
        )
