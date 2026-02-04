"""기본 카테고리 시드 커맨드.

사용법: python manage.py seed_categories

월급, 이체, 식비, 카페/간식, 교통 등 11개 기본 카테고리를
get_or_create 로 안전하게 생성한다 (중복 실행 가능).
"""

from django.core.management.base import BaseCommand
from transactions.models import Category


class Command(BaseCommand):
    help = "기본 카테고리(월급, 식비, 교통 등)를 초기 생성합니다."

    def handle(self, *args, **options):
        defaults = [
            ("월급", Category.INCOME),
            ("이체", Category.COMMON),
            ("기타수입", Category.INCOME),
            ("식비", Category.EXPENSE),
            ("카페/간식", Category.EXPENSE),
            ("교통", Category.EXPENSE),
            ("쇼핑", Category.EXPENSE),
            ("구독", Category.EXPENSE),
            ("주거/통신", Category.EXPENSE),
            ("의료/건강", Category.EXPENSE),
            ("기타지출", Category.EXPENSE),
        ]

        created = 0
        for name, cat_type in defaults:
            obj, was_created = Category.objects.get_or_create(
                name=name,
                defaults={"cat_type": cat_type},
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Done. created={created}"))
