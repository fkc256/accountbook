"""더미 데이터 생성 커맨드.

'fkc256' 유저에 대해 6개월치(2025.08 ~ 2026.01) 현실적인
가계부 데이터를 생성한다.

사용법: python manage.py generate_dummy_data

생성 내용:
  - 계좌 3개 (월급통장, 저축통장, 체크카드)
  - 정기 거래 7건 (월급, 월세, 구독 등)
  - 월별 수입·이체·고정지출·변동지출·특별지출 자동 생성
  - 재무 목표 설정 (저축 50만원, 월 소비 200만원)
"""

import random
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from transactions.models import (
    Account,
    Category,
    Goal,
    RecurringTransaction,
    Transaction,
)

User = get_user_model()


# ── 가맹점 사전 ──────────────────────────────────────────
MERCHANTS = {
    "편의점": ["CU 역삼점", "GS25 강남점", "세븐일레븐 삼성점", "이마트24 선릉점"],
    "카페": ["스타벅스 강남점", "투썸플레이스", "메가커피 역삼점", "컴포즈커피", "이디야 선릉점"],
    "식당": ["김밥천국", "맥도날드 강남점", "서브웨이 삼성점", "한솥도시락", "본죽", "이삭토스트",
             "풍년돈까스", "명동칼국수", "청기와타운", "마라탕집"],
    "배달": ["배달의민족", "쿠팡이츠", "요기요"],
    "마트": ["이마트 역삼점", "홈플러스 강남점", "쿠팡 로켓배송", "마켓컬리"],
    "지하철": ["서울교통공사", "수도권광역교통"],
    "버스": ["서울시버스", "경기버스"],
    "택시": ["카카오택시", "타다"],
    "주유": ["SK에너지 강남", "GS칼텍스 역삼", "현대오일뱅크"],
    "영화": ["CGV 강남", "롯데시네마 건대", "메가박스 코엑스"],
    "공연": ["인터파크 티켓", "예스24 티켓"],
    "게임": ["Steam", "닌텐도 e숍", "플레이스테이션 스토어"],
    "의류": ["유니클로 강남점", "자라 코엑스", "무신사 스토어", "에이블리"],
    "화장품": ["올리브영 역삼점", "이니스프리", "쿠팡 뷰티"],
    "생활용품": ["다이소 강남점", "아성다이소", "오늘의집"],
    "전자제품": ["쿠팡 디지털", "하이마트 강남", "애플스토어 가로수길"],
    "술집": ["포차 강남점", "몽탄 역삼", "맥주창고"],
    "기타": ["카카오페이", "네이버페이", "토스"],
    "자기계발": ["교보문고 강남점", "YES24", "알라딘", "클래스101", "탈잉", "인프런"],
}


def pick(key):
    """가맹점 사전에서 랜덤 가맹점명을 반환."""
    return random.choice(MERCHANTS[key])


def last_day(y, m):
    """해당 월의 마지막 날짜(28~31)를 반환."""
    nxt = date(y, m + 1, 1) if m < 12 else date(y + 1, 1, 1)
    return (nxt - timedelta(days=1)).day


class Command(BaseCommand):
    help = "fkc256 유저에 대해 6개월치 현실적인 더미 데이터를 생성합니다."

    cats = {}

    def ensure_categories(self):
        needed = {
            "월급": (Category.INCOME, False),
            "기타수입": (Category.INCOME, False),
            "이체": (Category.COMMON, False),
            "식비": (Category.EXPENSE, False),
            "카페/간식": (Category.EXPENSE, True),
            "교통": (Category.EXPENSE, False),
            "쇼핑": (Category.EXPENSE, True),
            "구독": (Category.EXPENSE, False),
            "주거/통신": (Category.EXPENSE, False),
            "의료/건강": (Category.EXPENSE, False),
            "기타지출": (Category.EXPENSE, False),
            "문화생활": (Category.EXPENSE, True),
            "유흥": (Category.EXPENSE, True),
            "자기계발": (Category.EXPENSE, True),
        }
        for name, (cat_type, is_sat) in needed.items():
            obj, created = Category.objects.get_or_create(
                name=name, defaults={"cat_type": cat_type, "is_satisfaction": is_sat},
            )
            if not created:
                # 기존 카테고리의 is_satisfaction 값도 갱신
                if obj.is_satisfaction != is_sat:
                    obj.is_satisfaction = is_sat
                    obj.save(update_fields=["is_satisfaction"])
            self.cats[name] = obj

    # ── 계좌 ─────────────────────────────────────────────
    def create_accounts(self, user):
        specs = [
            ("월급통장", "국민은행", "110456789012", 0),
            ("저축통장", "카카오뱅크", "333012345678", 0),
            ("체크카드(생활비통장)", "신한은행", "260987654321", 0),
        ]
        accounts = []
        for name, bank, num, balance in specs:
            acc = Account.objects.create(
                user=user, name=name, bank_name=bank,
                account_number=num, balance=balance,
            )
            accounts.append(acc)
        return accounts

    # ── 거래 추가 ────────────────────────────────────────
    def add_tx(self, user, account, category, tx_type, amount, dt, merchant="", memo=""):
        if tx_type == "OUT" and account.balance < amount:
            return None
        if tx_type == "IN":
            account.balance += amount
        else:
            account.balance -= amount

        self.tx_buffer.append(Transaction(
            user=user, account=account, category=category,
            tx_type=tx_type, amount=amount, balance_after=account.balance,
            occurred_at=dt, merchant=merchant, memo=memo,
        ))
        self.tx_count += 1
        return True

    def flush(self):
        if self.tx_buffer:
            Transaction.objects.bulk_create(self.tx_buffer)
            self.tx_buffer = []

    # ── 수입 ─────────────────────────────────────────────
    def gen_income(self, user, acc, dt):
        y, m = dt.year, dt.month
        pay_day = date(y, m, min(25, last_day(y, m)))
        self.add_tx(user, acc, self.cats["월급"], "IN", 3_000_000, pay_day,
                    "(주)테크스타트업", "월급")
        # 부수입 (40% 확률)
        if random.random() < 0.4:
            d = date(y, m, random.randint(1, last_day(y, m)))
            amt = random.randrange(50_000, 200_001, 10_000)
            self.add_tx(user, acc, self.cats["기타수입"], "IN", amt, d, "용돈/부수입", "부수입")

    # ── 이체: 월급통장 → 생활비통장 ─────────────────────
    def gen_transfer(self, user, acc_from, acc_to, dt):
        y, m = dt.year, dt.month
        d = date(y, m, 1)
        amt = 1_500_000
        self.add_tx(user, acc_from, self.cats["이체"], "OUT", amt, d,
                    "생활비 이체", "체크카드(생활비통장) 이체")
        self.add_tx(user, acc_to, self.cats["이체"], "IN", amt, d,
                    "생활비 입금", "월급통장에서 이체")

    # ── 저축 이체: 월급통장 → 저축통장 ──────────────────
    def gen_saving(self, user, acc_from, acc_to, dt):
        y, m = dt.year, dt.month
        d = date(y, m, min(26, last_day(y, m)))
        amt = random.randrange(300_000, 500_001, 50_000)
        self.add_tx(user, acc_from, self.cats["이체"], "OUT", amt, d,
                    "저축 이체", "저축통장 이체")
        self.add_tx(user, acc_to, self.cats["이체"], "IN", amt, d,
                    "저축 입금", "월급통장에서 이체")

    # ── 정기 지출 ────────────────────────────────────────
    def gen_fixed(self, user, acc_main, acc_card, dt):
        y, m = dt.year, dt.month
        fixed = [
            (1, "넷플릭스", 13_500, "구독", acc_card),
            (5, "월세", 500_000, "주거/통신", acc_main),
            (10, "SKT 통신비", 55_000, "주거/통신", acc_main),
            (15, "스포애니 헬스장", 60_000, "자기계발", acc_card),
            (20, "유튜브 프리미엄", 14_900, "구독", acc_card),
            (25, "삼성화재 자동차보험", 120_000, "기타지출", acc_main),
        ]
        for day, merchant, amount, cat_name, account in fixed:
            d = date(y, m, min(day, last_day(y, m)))
            self.add_tx(user, account, self.cats[cat_name], "OUT", amount, d,
                        merchant, "정기 결제")

    # ── 식비 (월 15~22건, ~35만원) ───────────────────────
    def gen_food(self, user, acc, dt):
        y, m = dt.year, dt.month
        ld = last_day(y, m)
        for _ in range(random.randint(15, 22)):
            d = date(y, m, random.randint(1, ld))
            weekend = d.weekday() >= 5
            r = random.random()

            if r < 0.25:
                merchant, amount, memo = pick("편의점"), random.randrange(2_000, 6_001, 500), "편의점"
            elif r < 0.45:
                merchant = pick("카페")
                amount = random.randrange(4_000, 6_501, 500)
                self.add_tx(user, acc, self.cats["카페/간식"], "OUT", amount, d, merchant, "카페")
                continue
            elif r < 0.70:
                merchant = pick("식당")
                amount = random.randrange(8_000, 20_001, 1_000)
                if weekend:
                    amount = int(amount * 1.3)
                memo = "외식"
            elif r < 0.85:
                merchant = pick("배달")
                amount = random.randrange(12_000, 28_001, 1_000)
                memo = "배달"
            else:
                merchant = pick("마트")
                amount = random.randrange(20_000, 80_001, 5_000)
                memo = "장보기"

            self.add_tx(user, acc, self.cats["식비"], "OUT", amount, d, merchant, memo)

    # ── 교통 (월 12~18건, ~8만원) ────────────────────────
    def gen_transport(self, user, acc, dt):
        y, m = dt.year, dt.month
        ld = last_day(y, m)
        for _ in range(random.randint(12, 18)):
            d = date(y, m, random.randint(1, ld))
            r = random.random()

            if r < 0.65:
                merchant = pick("지하철") if random.random() < 0.5 else pick("버스")
                amount = random.choice([1_400, 1_500, 2_500, 3_000])
                memo = "대중교통"
            elif r < 0.85:
                merchant = pick("택시")
                amount = random.randrange(6_000, 15_001, 1_000)
                memo = "택시"
            else:
                merchant = pick("주유")
                amount = random.randrange(50_000, 70_001, 5_000)
                memo = "주유"

            self.add_tx(user, acc, self.cats["교통"], "OUT", amount, d, merchant, memo)

    # ── 문화생활 (월 3~5건, ~6만원) ──────────────────────
    def gen_culture(self, user, acc, dt):
        y, m = dt.year, dt.month
        ld = last_day(y, m)
        for _ in range(random.randint(3, 5)):
            d = date(y, m, random.randint(1, ld))
            r = random.random()

            if r < 0.45:
                merchant, amount, memo = pick("영화"), 15_000, "영화 관람"
            elif r < 0.70:
                merchant = pick("게임")
                amount = random.randrange(10_000, 30_001, 5_000)
                memo = "게임 결제"
            else:
                merchant = pick("공연")
                amount = random.randrange(20_000, 50_001, 10_000)
                memo = "공연/전시"

            self.add_tx(user, acc, self.cats["문화생활"], "OUT", amount, d, merchant, memo)

    # ── 쇼핑 (월 3~6건, ~15만원) ─────────────────────────
    def gen_shopping(self, user, acc, dt):
        y, m = dt.year, dt.month
        ld = last_day(y, m)
        for _ in range(random.randint(3, 6)):
            d = date(y, m, random.randint(1, ld))
            r = random.random()

            if r < 0.35:
                merchant = pick("의류")
                amount = random.randrange(20_000, 80_001, 5_000)
                memo = "의류 구매"
            elif r < 0.55:
                merchant = pick("화장품")
                amount = random.randrange(10_000, 40_001, 5_000)
                memo = "화장품"
            elif r < 0.80:
                merchant = pick("생활용품")
                amount = random.randrange(5_000, 30_001, 5_000)
                memo = "생활용품"
            else:
                merchant = pick("전자제품")
                amount = random.randrange(50_000, 200_001, 10_000)
                memo = "전자제품"

            self.add_tx(user, acc, self.cats["쇼핑"], "OUT", amount, d, merchant, memo)

    # ── 자기계발 (월 2~4건, ~5만원) ──────────────────────
    def gen_selfdev(self, user, acc, dt):
        y, m = dt.year, dt.month
        ld = last_day(y, m)
        for _ in range(random.randint(2, 4)):
            d = date(y, m, random.randint(1, ld))
            merchant = pick("자기계발")
            r = random.random()

            if r < 0.50:
                amount = random.randrange(10_000, 30_001, 5_000)
                memo = "도서 구매"
            else:
                amount = random.randrange(20_000, 60_001, 10_000)
                memo = "온라인 강의"

            self.add_tx(user, acc, self.cats["자기계발"], "OUT", amount, d, merchant, memo)

    # ── 기타 (월 3~5건, ~5만원) ──────────────────────────
    def gen_misc(self, user, acc, dt):
        y, m = dt.year, dt.month
        ld = last_day(y, m)
        for _ in range(random.randint(3, 5)):
            d = date(y, m, random.randint(1, ld))
            merchant = pick("기타")
            amount = random.randrange(5_000, 30_001, 5_000)
            self.add_tx(user, acc, self.cats["기타지출"], "OUT", amount, d, merchant, "기타 결제")

    # ── 금요일 유흥 (60% 확률, ~5만원) ───────────────────
    def gen_friday(self, user, acc, dt):
        y, m = dt.year, dt.month
        ld = last_day(y, m)
        for day in range(1, ld + 1):
            d = date(y, m, day)
            if d.weekday() == 4 and random.random() < 0.5:
                merchant = pick("술집")
                amount = random.randrange(20_000, 60_001, 5_000)
                self.add_tx(user, acc, self.cats["유흥"], "OUT", amount, d,
                            merchant, "금요일 회식/술자리")

    # ── 특별 지출 ────────────────────────────────────────
    def gen_specials(self, user, acc, dt):
        y, m = dt.year, dt.month
        if m == 9:
            self.add_tx(user, acc, self.cats["기타지출"], "OUT", 300_000,
                        date(y, m, 15), "명절 선물", "추석 명절 지출")
        elif m == 1:
            self.add_tx(user, acc, self.cats["기타지출"], "OUT", 300_000,
                        date(y, m, 25), "명절 선물", "설 명절 지출")

    def gen_big(self, user, acc):
        events = [
            (date(2025, 10, 12), 350_000, "하나투어", "제주도 여행 (숙소)"),
            (date(2025, 12, 20), 250_000, "크리스마스 선물", "연말 선물"),
        ]
        for d, amount, merchant, memo in events:
            self.add_tx(user, acc, self.cats["쇼핑"], "OUT", amount, d, merchant, memo)

    # ── 정기 거래 등록 ───────────────────────────────────
    def create_recurring(self, user, acc_main, acc_card):
        specs = [
            (1, "넷플릭스", 13_500, "OUT", "구독", acc_card),
            (5, "월세", 500_000, "OUT", "주거/통신", acc_main),
            (10, "SKT 통신비", 55_000, "OUT", "주거/통신", acc_main),
            (15, "스포애니 헬스장", 60_000, "OUT", "자기계발", acc_card),
            (20, "유튜브 프리미엄", 14_900, "OUT", "구독", acc_card),
            (25, "삼성화재 자동차보험", 120_000, "OUT", "기타지출", acc_main),
            (25, "(주)테크스타트업", 3_000_000, "IN", "월급", acc_main),
        ]
        count = 0
        for day, merchant, amount, tx_type, cat_name, account in specs:
            _, created = RecurringTransaction.objects.get_or_create(
                user=user, account=account, recurring_day=day, merchant=merchant,
                defaults={
                    "category": self.cats[cat_name], "tx_type": tx_type,
                    "amount": amount, "start_date": date(2025, 8, 1),
                    "is_active": True,
                    "memo": "정기 결제" if tx_type == "OUT" else "월급",
                },
            )
            if created:
                count += 1
        return count

    # ── 메인 ─────────────────────────────────────────────
    def handle(self, *args, **options):
        try:
            user = User.objects.get(username="fkc256")
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                "오류: username 'fkc256' 유저가 존재하지 않습니다."))
            return

        self.tx_buffer = []
        self.tx_count = 0

        self.stdout.write(self.style.NOTICE("카테고리 준비 중..."))
        self.ensure_categories()

        self.stdout.write(self.style.NOTICE("기존 데이터 정리 중..."))
        Transaction.objects.filter(user=user).delete()
        RecurringTransaction.objects.filter(user=user).delete()
        Account.objects.filter(user=user).delete()

        self.stdout.write(self.style.NOTICE("계좌 생성 중..."))
        acc_main, acc_save, acc_card = self.create_accounts(user)

        self.stdout.write(self.style.NOTICE("정기 거래 등록 중..."))
        rec_count = self.create_recurring(user, acc_main, acc_card)
        self.stdout.write(f"  정기 거래 {rec_count}건 등록")

        self.stdout.write(self.style.NOTICE("목표 설정 중..."))
        Goal.objects.update_or_create(user=user, defaults={
            "target_saving": 500_000, "monthly_spending_limit": 2_000_000,
        })

        months = [
            (2025, 8), (2025, 9), (2025, 10),
            (2025, 11), (2025, 12), (2026, 1),
        ]
        random.seed(42)

        total_income_all = 0
        total_expense_all = 0

        for y, m in months:
            dt = date(y, m, 1)
            self.stdout.write(self.style.NOTICE(f"\n── {y}년 {m}월 생성 중... ──"))
            before = self.tx_count

            # 1) 수입
            self.gen_income(user, acc_main, dt)

            # 2) 이체: 월급통장 → 생활비통장 (매달 1일)
            self.gen_transfer(user, acc_main, acc_card, dt)

            # 3) 정기 지출
            self.gen_fixed(user, acc_main, acc_card, dt)

            # 4) 변동 지출 (체크카드)
            self.gen_food(user, acc_card, dt)
            self.gen_transport(user, acc_card, dt)
            self.gen_culture(user, acc_card, dt)
            self.gen_shopping(user, acc_card, dt)
            self.gen_selfdev(user, acc_card, dt)
            self.gen_misc(user, acc_card, dt)
            self.gen_friday(user, acc_card, dt)

            # 5) 특별 지출 (월급통장)
            self.gen_specials(user, acc_main, dt)

            # 6) 저축 이체 (월급 다음날)
            self.gen_saving(user, acc_main, acc_save, dt)

            month_count = self.tx_count - before
            self.stdout.write(f"  {month_count}건 생성")

        self.stdout.write(self.style.NOTICE("\n특별 지출 이벤트 생성 중..."))
        self.gen_big(user, acc_main)

        self.stdout.write(self.style.NOTICE("DB에 저장 중..."))
        self.flush()

        # 최종 잔액 저장
        for acc in [acc_main, acc_save, acc_card]:
            acc.save(update_fields=["balance"])

        # 수입/지출 합계 계산
        income_total = sum(
            t.amount for t in Transaction.objects.filter(user=user, tx_type="IN")
            if t.category and t.category.name != "이체"
        )
        expense_total = sum(
            t.amount for t in Transaction.objects.filter(user=user, tx_type="OUT")
            if t.category and t.category.name != "이체"
        )

        self.stdout.write(self.style.SUCCESS(
            f"\n완료! 총 {self.tx_count}건의 거래 데이터가 생성되었습니다."
        ))
        self.stdout.write(f"  총 수입 (이체 제외): {income_total:,}원")
        self.stdout.write(f"  총 지출 (이체 제외): {expense_total:,}원")
        self.stdout.write(f"  순이익: {income_total - expense_total:,}원")
        self.stdout.write("")
        for acc in [acc_main, acc_save, acc_card]:
            self.stdout.write(f"  {acc.name}: {acc.balance:,}원")
