from http import HTTPStatus
from unittest.mock import patch

from django.core import mail
from django.test import TransactionTestCase, override_settings

from .models import User


class RegistrationTest(TransactionTestCase):
    @override_settings(DISABLE_REGISTRATION=True)
    def test_registration_disabled(self):
        with self.assertNumQueries(0):
            response = self.client.post("/accounts/register/")
        self.assertContains(
            response, "Registration is currently closed", status_code=503
        )

    @override_settings(DISABLE_REGISTRATION=False)
    def test_blank_email(self):
        with self.assertNumQueries(0):
            response = self.client.post("/accounts/register/")
        self.assertContains(response, "This field is required")

    @override_settings(
        DISABLE_REGISTRATION=False,
        PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    )
    @patch("turnstile.fields.TurnstileField.validate", return_value=True)
    def test_registration(self, mocked_validate):
        response = self.client.get("/accounts/register/")
        self.assertContains(response, "Email address")

        # IP address banned:
        User.objects.create(trusted=False, ip_address="6.6.6.6")
        with self.assertNumQueries(1):
            # create new account
            response = self.client.post(
                "/accounts/register/",
                {"email": "rufus@herring.pizza", "turnstile": "foo"},
                headers={"CF-Connecting-IP": "6.6.6.6"},
            )
            self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

        # create new account successfully:
        with self.assertNumQueries(4):
            response = self.client.post(
                "/accounts/register/",
                {"email": "rufus@herring.pizza", "turnstile": "foo"},
                headers={"CF-Connecting-IP": "1.2.3.4"},
            )
        self.assertContains(response, "Check your email (rufus@herring.pizza")
        self.assertEqual("bustimes.org account", mail.outbox[0].subject)
        self.assertIn("a bustimes.org account", mail.outbox[0].body)

        user = User.objects.get(email="rufus@herring.pizza")
        self.assertEqual(user.ip_address, "1.2.3.4")
        user.is_active = False
        user.save()

        with self.assertNumQueries(2):
            # reactivate existing account
            response = self.client.post(
                "/accounts/register/",
                {"email": "RUFUS@HeRRInG.piZZa", "turnstile": "foo"},
            )

        user.refresh_from_db()
        self.assertEqual(user.username, "rufus@herring.pizza")
        self.assertEqual(user.email, "rufus@herring.pizza")
        self.assertIs(True, user.is_active)
        self.assertEqual(str(user), str(user.id))

        with self.assertNumQueries(2):
            response = self.client.post(
                "/accounts/register/",
                {"email": "ROY@HotMail.com", "turnstile": "foo"},
            )

        user = User.objects.get(email__iexact="ROY@HotMail.com")
        self.assertEqual(user.username, "ROY@HotMail.com")
        self.assertEqual(user.email, "ROY@hotmail.com")

        self.assertContains(response, "Check your email (ROY@hotmail.com")
        self.assertEqual(3, len(mail.outbox))

        # username (email address) should be case insensitive
        user.set_password("swim green twenty eggs")
        user.save()
        with self.assertNumQueries(9):
            response = self.client.post(
                "/accounts/login/",
                {"username": "roY@hoTmail.com", "password": "swim green twenty eggs"},
            )
            self.assertEqual(302, response.status_code)

    def test_update_user(self):
        super_user = User.objects.create(
            username="josh", is_staff=True, is_superuser=True, email="j@example.com"
        )
        other_user = User.objects.create(
            username="ken@example.com",
            trusted=None,
            email="ken@example.com",
        )

        # super user sees change link:

        self.client.force_login(super_user)

        response = self.client.get(other_user.get_absolute_url())

        self.assertContains(response, "/change/")

        # set permissions
        with self.assertNumQueries(6):
            response = self.client.post(other_user.get_absolute_url())

        # trust/distrust in admin
        response = self.client.post(
            "/admin/accounts/user/",
            {
                "action": "trust",
                "_selected_action": [other_user.id],
            },
        )
        other_user.refresh_from_db()
        self.assertTrue(other_user.trusted)

        response = self.client.post(
            "/admin/accounts/user/",
            {
                "action": "distrust",
                "_selected_action": [other_user.id],
            },
        )
        other_user.refresh_from_db()
        self.assertFalse(other_user.trusted)

        self.client.force_login(other_user)

        # normal user can't see email addresses
        response = self.client.get(super_user.get_absolute_url())
        self.assertNotContains(response, "ken@example.com")

        # set username:

        response = self.client.post(
            other_user.get_absolute_url(), {"name": "kenton_schweppes"}
        )
        other_user.refresh_from_db()
        self.assertEqual(other_user.username, "kenton_schweppes")

        # try setting a looong username:
        response = self.client.post(
            other_user.get_absolute_url(),
            {"name": "Hubert Blaine Wolfeschlegelsteinhausenbergerdorff Sr."},
        )
        self.assertContains(
            response, ">Ensure this value has at most 50 characters (it has 53).</"
        )

        # try copying someone else's username
        response = self.client.post(other_user.get_absolute_url(), {"name": "josh"})
        self.assertContains(response, ">Username taken<")

        self.assertContains(response, "That's you!")

        self.client.post(other_user.get_absolute_url(), {"name": ""})
        other_user.refresh_from_db()
        self.assertEqual(other_user.username, "ken@example.com")

        # user can delete own account:

        with self.assertNumQueries(4):
            self.client.post(other_user.get_absolute_url(), {"confirm_delete": False})
            # confirm delete not ticked
        other_user.refresh_from_db()
        self.assertTrue(other_user.is_active)

        with self.assertNumQueries(5):
            self.client.post(other_user.get_absolute_url(), {"confirm_delete": "on"})
        other_user.refresh_from_db()
        self.assertFalse(other_user.is_active)

    def test_password_reset(self):
        with self.assertNumQueries(0):
            response = self.client.get("/accounts/password_reset/")
        self.assertContains(response, "Reset your password")
        self.assertContains(response, "Email address")

        with self.assertNumQueries(1):
            response = self.client.post(
                "/accounts/password_reset/",
                {
                    "email": "rufus@herring.pizza",
                },
            )
        self.assertEqual(response.url, "/accounts/password_reset/done/")

        with self.assertNumQueries(0):
            response = self.client.get(response.url)
        self.assertContains(
            response,
            "<p>We’ve emailed you instructions for setting your password, if an account exists with the email you "
            "entered. You should receive them shortly.</p>",
        )
        self.assertEqual([], mail.outbox)
