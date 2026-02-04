from django.test import TestCase, Client
from django.contrib.auth.models import User


class AuthTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="pass1234!")

    def test_login_page_loads(self):
        res = self.client.get("/accounts/login/")
        self.assertEqual(res.status_code, 200)

    def test_signup_page_loads(self):
        res = self.client.get("/accounts/signup/")
        self.assertEqual(res.status_code, 200)

    def test_login_success(self):
        res = self.client.post("/accounts/login/", {
            "username": "testuser",
            "password": "pass1234!",
        })
        self.assertEqual(res.status_code, 302)

    def test_login_fail(self):
        res = self.client.post("/accounts/login/", {
            "username": "testuser",
            "password": "wrong",
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "올바르지 않습니다")

    def test_signup_creates_user(self):
        res = self.client.post("/accounts/signup/", {
            "username": "newuser",
            "password1": "Str0ngP@ss!",
            "password2": "Str0ngP@ss!",
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_protected_page_redirects_to_login(self):
        res = self.client.get("/transactions/accounts/")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/accounts/login/", res.url)

    def test_logout(self):
        self.client.login(username="testuser", password="pass1234!")
        res = self.client.get("/accounts/logout/")
        self.assertEqual(res.status_code, 302)
