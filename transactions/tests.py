from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import Account, Category, Transaction, RecurringTransaction


class AccountCRUDTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="pass1234!")
        self.other = User.objects.create_user(username="u2", password="pass1234!")
        self.client.login(username="u1", password="pass1234!")
        self.account = Account.objects.create(
            user=self.user, name="생활비", bank_name="국민",
            account_number="1234567890", balance=100000,
        )

    def test_account_list(self):
        res = self.client.get("/transactions/accounts/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "생활비")

    def test_account_create(self):
        res = self.client.post("/transactions/accounts/new/", {
            "name": "적금", "bank_name": "신한",
            "account_number": "9876543210", "balance": 0, "is_active": True,
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Account.objects.filter(name="적금", user=self.user).exists())

    def test_account_detail(self):
        res = self.client.get(f"/transactions/accounts/{self.account.pk}/")
        self.assertEqual(res.status_code, 200)

    def test_account_update(self):
        res = self.client.post(f"/transactions/accounts/{self.account.pk}/edit/", {
            "name": "수정된이름", "bank_name": "국민",
            "account_number": "1234567890", "balance": 100000, "is_active": True,
        })
        self.assertEqual(res.status_code, 302)
        self.account.refresh_from_db()
        self.assertEqual(self.account.name, "수정된이름")

    def test_account_delete(self):
        res = self.client.post(f"/transactions/accounts/{self.account.pk}/delete/")
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Account.objects.filter(pk=self.account.pk).exists())

    def test_other_user_account_blocked(self):
        other_acc = Account.objects.create(
            user=self.other, name="남의계좌", bank_name="하나",
            account_number="0000000000",
        )
        res = self.client.get(f"/transactions/accounts/{other_acc.pk}/")
        self.assertEqual(res.status_code, 404)

    def test_masked_account_number(self):
        masked = self.account.masked_account_number()
        self.assertNotIn("1234567890", masked)
        self.assertIn("*", masked)


class TransactionCRUDTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="pass1234!")
        self.other = User.objects.create_user(username="u2", password="pass1234!")
        self.client.login(username="u1", password="pass1234!")
        self.account = Account.objects.create(
            user=self.user, name="생활비", bank_name="국민",
            account_number="1234567890", balance=1000000,
        )
        self.category = Category.objects.create(name="식비", cat_type="OUT")
        self.tx = Transaction.objects.create(
            user=self.user, account=self.account, category=self.category,
            tx_type="OUT", amount=15000, occurred_at="2026-01-15",
            merchant="카페", memo="커피",
        )

    def test_transaction_list(self):
        res = self.client.get("/transactions/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "15,000")

    def test_transaction_create(self):
        res = self.client.post("/transactions/new/", {
            "account": self.account.pk,
            "category": self.category.pk,
            "tx_type": "IN",
            "amount": "50000",
            "occurred_at": "2026-01-20",
            "merchant": "회사",
            "memo": "용돈",
        })
        self.assertEqual(res.status_code, 302)
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 2)

    def test_transaction_detail(self):
        res = self.client.get(f"/transactions/{self.tx.pk}/")
        self.assertEqual(res.status_code, 200)

    def test_transaction_update(self):
        res = self.client.post(f"/transactions/{self.tx.pk}/edit/", {
            "account": self.account.pk,
            "category": self.category.pk,
            "tx_type": "OUT",
            "amount": "20000",
            "occurred_at": "2026-01-15",
            "merchant": "카페",
            "memo": "수정됨",
        })
        self.assertEqual(res.status_code, 302)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.amount, 20000)

    def test_transaction_delete(self):
        res = self.client.post(f"/transactions/{self.tx.pk}/delete/")
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Transaction.objects.filter(pk=self.tx.pk).exists())

    def test_other_user_transaction_blocked(self):
        other_acc = Account.objects.create(
            user=self.other, name="남의계좌", bank_name="하나",
            account_number="0000000000",
        )
        other_tx = Transaction.objects.create(
            user=self.other, account=other_acc,
            tx_type="IN", amount=99999, occurred_at="2026-01-01",
        )
        res = self.client.get(f"/transactions/{other_tx.pk}/")
        self.assertEqual(res.status_code, 404)


class TransactionFilterTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="pass1234!")
        self.client.login(username="u1", password="pass1234!")
        self.account = Account.objects.create(
            user=self.user, name="생활비", bank_name="국민",
            account_number="1234567890",
        )
        self.cat = Category.objects.create(name="식비", cat_type="OUT")
        Transaction.objects.create(
            user=self.user, account=self.account, category=self.cat,
            tx_type="OUT", amount=10000, occurred_at="2026-01-10",
            memo="점심",
        )
        Transaction.objects.create(
            user=self.user, account=self.account,
            tx_type="IN", amount=50000, occurred_at="2026-01-20",
            memo="용돈",
        )

    def test_filter_by_tx_type(self):
        res = self.client.get("/transactions/?tx_type=IN")
        self.assertContains(res, "50,000")
        self.assertNotContains(res, "10,000")

    def test_filter_by_date_range(self):
        res = self.client.get("/transactions/?date_from=2026-01-15&date_to=2026-01-31")
        self.assertContains(res, "50,000")
        self.assertNotContains(res, "10,000")

    def test_filter_by_category(self):
        res = self.client.get(f"/transactions/?category={self.cat.pk}")
        self.assertContains(res, "10,000")
        self.assertNotContains(res, "50,000")

    def test_search_keyword(self):
        res = self.client.get("/transactions/?q=점심")
        self.assertContains(res, "10,000")
        self.assertNotContains(res, "50,000")


class RecurringTransactionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="pass1234!")
        self.client.login(username="u1", password="pass1234!")
        self.account = Account.objects.create(
            user=self.user, name="생활비", bank_name="국민",
            account_number="1234567890", balance=3000000,
        )
        self.cat = Category.objects.create(name="구독", cat_type="OUT")

    def test_recurring_create(self):
        res = self.client.post("/transactions/recurring/new/", {
            "account": self.account.pk,
            "category": self.cat.pk,
            "tx_type": "OUT",
            "amount": 13500,
            "recurring_day": 1,
            "merchant": "넷플릭스",
            "memo": "구독료",
            "start_date": "2026-01-01",
            "is_active": True,
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(RecurringTransaction.objects.filter(user=self.user).exists())

    def test_recurring_list(self):
        RecurringTransaction.objects.create(
            user=self.user, account=self.account, category=self.cat,
            tx_type="OUT", amount=13500, recurring_day=1,
            start_date="2026-01-01",
        )
        res = self.client.get("/transactions/recurring/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "13,500")

    def test_recurring_toggle(self):
        rec = RecurringTransaction.objects.create(
            user=self.user, account=self.account,
            tx_type="IN", amount=3000000, recurring_day=25,
            start_date="2026-01-01", is_active=True,
        )
        self.client.post(f"/transactions/recurring/{rec.pk}/toggle/")
        rec.refresh_from_db()
        self.assertFalse(rec.is_active)

    def test_recurring_delete(self):
        rec = RecurringTransaction.objects.create(
            user=self.user, account=self.account,
            tx_type="OUT", amount=500000, recurring_day=5,
            start_date="2026-01-01",
        )
        res = self.client.post(f"/transactions/recurring/{rec.pk}/delete/")
        self.assertEqual(res.status_code, 302)
        self.assertFalse(RecurringTransaction.objects.filter(pk=rec.pk).exists())

    def test_process_recurring_command(self):
        from datetime import date
        today = date.today()
        rec = RecurringTransaction.objects.create(
            user=self.user, account=self.account, category=self.cat,
            tx_type="OUT", amount=500000, recurring_day=today.day,
            merchant="집주인", memo="월세",
            start_date="2026-01-01", is_active=True,
        )
        from django.core.management import call_command
        call_command("process_recurring")

        # Transaction이 생성되었는지 확인
        tx = Transaction.objects.filter(user=self.user, memo__contains="월세")
        self.assertEqual(tx.count(), 1)
        self.assertEqual(tx.first().amount, 500000)

        # 잔액이 차감되었는지 확인
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 2500000)

        # last_executed 갱신 확인
        rec.refresh_from_db()
        self.assertEqual(rec.last_executed, today)

    def test_process_recurring_no_duplicate(self):
        from datetime import date
        today = date.today()
        RecurringTransaction.objects.create(
            user=self.user, account=self.account,
            tx_type="IN", amount=100000, recurring_day=today.day,
            start_date="2026-01-01", is_active=True,
            last_executed=today,
        )
        from django.core.management import call_command
        call_command("process_recurring")

        # 이미 실행된 건은 중복 생성 안 됨
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 0)


class BalanceAutoUpdateTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="pass1234!")
        self.client.login(username="u1", password="pass1234!")
        self.account = Account.objects.create(
            user=self.user, name="생활비", bank_name="국민",
            account_number="1234567890", balance=1000000,
        )
        self.cat = Category.objects.create(name="식비", cat_type="OUT")

    def test_create_income_increases_balance(self):
        self.client.post("/transactions/new/", {
            "account": self.account.pk,
            "tx_type": "IN",
            "amount": 500000,
            "occurred_at": "2026-01-20",
        })
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 1500000)

    def test_create_expense_decreases_balance(self):
        self.client.post("/transactions/new/", {
            "account": self.account.pk,
            "tx_type": "OUT",
            "amount": 300000,
            "occurred_at": "2026-01-20",
        })
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 700000)

    def test_balance_after_recorded(self):
        self.client.post("/transactions/new/", {
            "account": self.account.pk,
            "tx_type": "OUT",
            "amount": 200000,
            "occurred_at": "2026-01-20",
        })
        tx = Transaction.objects.filter(user=self.user).first()
        self.assertEqual(tx.balance_after, 800000)

    def test_delete_reverses_balance(self):
        self.client.post("/transactions/new/", {
            "account": self.account.pk,
            "tx_type": "OUT",
            "amount": 400000,
            "occurred_at": "2026-01-20",
        })
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 600000)

        tx = Transaction.objects.filter(user=self.user).first()
        self.client.post(f"/transactions/{tx.pk}/delete/")
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 1000000)

    def test_update_recalculates_balance(self):
        # 1) 출금 30만원 생성
        self.client.post("/transactions/new/", {
            "account": self.account.pk,
            "tx_type": "OUT",
            "amount": 300000,
            "occurred_at": "2026-01-20",
        })
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 700000)

        # 2) 50만원으로 수정
        tx = Transaction.objects.filter(user=self.user).first()
        self.client.post(f"/transactions/{tx.pk}/edit/", {
            "account": self.account.pk,
            "tx_type": "OUT",
            "amount": 500000,
            "occurred_at": "2026-01-20",
        })
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 500000)

    def test_insufficient_balance_warning(self):
        res = self.client.post("/transactions/new/", {
            "account": self.account.pk,
            "tx_type": "OUT",
            "amount": 9999999,
            "occurred_at": "2026-01-20",
        })
        # 경고 표시, 저장 안 됨
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "잔액이 부족합니다")
        self.assertEqual(Transaction.objects.filter(user=self.user).count(), 0)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 1000000)

    def test_insufficient_balance_confirm_saves(self):
        # confirm=1 포함하면 저장됨
        res = self.client.post("/transactions/new/", {
            "account": self.account.pk,
            "tx_type": "OUT",
            "amount": 9999999,
            "occurred_at": "2026-01-20",
            "confirm": "1",
        })
        self.assertEqual(res.status_code, 302)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 1000000 - 9999999)
