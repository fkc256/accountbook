from django.test import TestCase, Client
from django.contrib.auth.models import User

from transactions.models import Account, Category, Transaction


class DashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="pass1234!")
        self.other = User.objects.create_user(username="u2", password="pass1234!")
        self.client.login(username="u1", password="pass1234!")

        self.account = Account.objects.create(
            user=self.user, name="생활비", bank_name="국민",
            account_number="1234567890", balance=1000000,
        )
        self.cat_food = Category.objects.create(name="식비", cat_type="OUT")
        self.cat_salary = Category.objects.create(name="급여", cat_type="IN")

        # u1 거래 데이터 (2026-01)
        Transaction.objects.create(
            user=self.user, account=self.account, category=self.cat_salary,
            tx_type="IN", amount=3000000, occurred_at="2026-01-25",
        )
        Transaction.objects.create(
            user=self.user, account=self.account, category=self.cat_food,
            tx_type="OUT", amount=150000, occurred_at="2026-01-10",
        )
        Transaction.objects.create(
            user=self.user, account=self.account, category=self.cat_food,
            tx_type="OUT", amount=100000, occurred_at="2026-01-20",
        )

        # u2 거래 데이터 (대시보드에 보이면 안 됨)
        other_acc = Account.objects.create(
            user=self.other, name="다른계좌", bank_name="신한",
            account_number="0000000000",
        )
        Transaction.objects.create(
            user=self.other, account=other_acc,
            tx_type="IN", amount=9999999, occurred_at="2026-01-15",
        )

    def test_dashboard_requires_login(self):
        self.client.logout()
        res = self.client.get("/dashboard/")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/accounts/login/", res.url)

    def test_dashboard_loads(self):
        res = self.client.get("/dashboard/")
        self.assertEqual(res.status_code, 200)

    def test_dashboard_current_month(self):
        res = self.client.get("/dashboard/?month=2026-01")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["total_income"], 3000000)
        self.assertEqual(res.context["total_expense"], 250000)
        self.assertEqual(res.context["net"], 2750000)

    def test_dashboard_month_param(self):
        # 2026-02에는 거래가 없으므로 모두 0
        res = self.client.get("/dashboard/?month=2026-02")
        self.assertEqual(res.context["total_income"], 0)
        self.assertEqual(res.context["total_expense"], 0)
        self.assertEqual(res.context["net"], 0)

    def test_dashboard_invalid_month_param(self):
        # 잘못된 month 파라미터 → 현재 달로 fallback
        res = self.client.get("/dashboard/?month=invalid")
        self.assertEqual(res.status_code, 200)
        # 에러 없이 정상 렌더링 되는지 확인
        self.assertIn("year", res.context)
        self.assertIn("month", res.context)

    def test_dashboard_category_summary(self):
        res = self.client.get("/dashboard/?month=2026-01")
        summary = list(res.context["category_summary"])
        # 식비 카테고리 합계 확인
        food_entry = next(
            (s for s in summary if s["category__name"] == "식비"), None
        )
        self.assertIsNotNone(food_entry)
        self.assertEqual(food_entry["total"], 250000)

    def test_dashboard_excludes_other_user(self):
        # u2의 9,999,999원 거래가 보이면 안 됨
        res = self.client.get("/dashboard/?month=2026-01")
        self.assertNotEqual(res.context["total_income"], 9999999)
        self.assertEqual(res.context["total_income"], 3000000)

    def test_dashboard_empty_month(self):
        # 거래가 없는 달
        res = self.client.get("/dashboard/?month=2025-06")
        self.assertEqual(res.context["total_income"], 0)
        self.assertEqual(res.context["total_expense"], 0)
        self.assertEqual(res.context["category_summary"].count(), 0)
