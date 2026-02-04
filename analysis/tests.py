from django.test import TestCase, Client
from django.contrib.auth.models import User

from transactions.models import Account, Category, Transaction, Goal


class InMoneyViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="pass1234!")
        self.client.login(username="u1", password="pass1234!")

        self.account = Account.objects.create(
            user=self.user, name="생활비", bank_name="국민",
            account_number="1234567890", balance=5000000,
        )
        self.cat = Category.objects.create(name="식비", cat_type="OUT")

        Transaction.objects.create(
            user=self.user, account=self.account, category=self.cat,
            tx_type="OUT", amount=200000, occurred_at="2026-01-10",
        )
        Transaction.objects.create(
            user=self.user, account=self.account,
            tx_type="IN", amount=3000000, occurred_at="2026-01-25",
        )

    def test_inmoney_requires_login(self):
        self.client.logout()
        res = self.client.get("/inmoney/")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/accounts/login/", res.url)

    def test_inmoney_loads(self):
        res = self.client.get("/inmoney/")
        self.assertEqual(res.status_code, 200)

    def test_inmoney_context_values(self):
        res = self.client.get("/inmoney/")
        self.assertEqual(res.context["total_income"], 3000000)
        self.assertEqual(res.context["total_expense"], 200000)
        self.assertEqual(res.context["net"], 2800000)

    def test_inmoney_financial_score(self):
        res = self.client.get("/inmoney/")
        score = res.context["financial_score"]
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        self.assertIn(res.context["grade"], ["S", "A", "B", "C", "D", "F"])

    def test_inmoney_no_data(self):
        # 데이터 없는 사용자
        user2 = User.objects.create_user(username="empty", password="pass1234!")
        self.client.login(username="empty", password="pass1234!")
        res = self.client.get("/inmoney/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["total_income"], 0)
        self.assertEqual(res.context["total_expense"], 0)

    def test_inmoney_excludes_other_user(self):
        other = User.objects.create_user(username="u2", password="pass1234!")
        other_acc = Account.objects.create(
            user=other, name="남의계좌", bank_name="하나",
            account_number="0000000000",
        )
        Transaction.objects.create(
            user=other, account=other_acc,
            tx_type="IN", amount=99999999, occurred_at="2026-01-15",
        )
        res = self.client.get("/inmoney/")
        self.assertNotEqual(res.context["total_income"], 99999999)


class GoalViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="pass1234!")
        self.client.login(username="u1", password="pass1234!")

    def test_goal_form_loads(self):
        res = self.client.get("/inmoney/goal/")
        self.assertEqual(res.status_code, 200)

    def test_goal_create(self):
        res = self.client.post("/inmoney/goal/", {
            "target_saving": 500000,
            "monthly_spending_limit": 1000000,
        })
        self.assertEqual(res.status_code, 302)
        goal = Goal.objects.get(user=self.user)
        self.assertEqual(goal.target_saving, 500000)
        self.assertEqual(goal.monthly_spending_limit, 1000000)

    def test_goal_update(self):
        Goal.objects.create(
            user=self.user, target_saving=100000, monthly_spending_limit=500000,
        )
        res = self.client.post("/inmoney/goal/", {
            "target_saving": 300000,
            "monthly_spending_limit": 800000,
        })
        self.assertEqual(res.status_code, 302)
        goal = Goal.objects.get(user=self.user)
        self.assertEqual(goal.target_saving, 300000)

    def test_goal_requires_login(self):
        self.client.logout()
        res = self.client.get("/inmoney/goal/")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/accounts/login/", res.url)


class GptAnalysisViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="pass1234!")
        self.client.login(username="u1", password="pass1234!")

    def test_gpt_analysis_requires_login(self):
        self.client.logout()
        res = self.client.post("/inmoney/gpt-analysis/")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/accounts/login/", res.url)

    def test_gpt_analysis_get_not_allowed(self):
        res = self.client.get("/inmoney/gpt-analysis/")
        self.assertEqual(res.status_code, 405)
