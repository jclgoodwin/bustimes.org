from django.test import TestCase
from django.core import mail
from .models import User


class RegistrationTest(TestCase):
    def test_blank_email(self):
        with self.assertNumQueries(0):
            response = self.client.post("/accounts/register/")
        self.assertContains(response, "This field is required")

    def test_registration(self):
        response = self.client.get("/accounts/register/")
        self.assertContains(response, "Email address")

        with self.assertNumQueries(2):
            response = self.client.post(
                "/accounts/register/",
                {
                    "email": "rufus@herring.pizza",
                },
            )
        self.assertContains(response, "Check your email (rufus@herring.pizza")
        self.assertEquals("bustimes.org account", mail.outbox[0].subject)
        self.assertIn("a bustimes.org account", mail.outbox[0].body)

        with self.assertNumQueries(1):
            response = self.client.post(
                "/accounts/register/",
                {
                    "email": "RUFUS@HeRRInG.piZZa",
                },
            )

        user = User.objects.get()
        self.assertEqual(user.username, "rufus@herring.pizza")
        self.assertEqual(user.email, "rufus@herring.pizza")
        self.assertEqual(str(user), str(user.id))

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
        self.assertEquals(response.url, "/accounts/password_reset/done/")

        with self.assertNumQueries(0):
            response = self.client.get(response.url)
        self.assertContains(
            response,
            "<p>We’ve emailed you instructions for setting your password, if an account exists with the email you "
            "entered. You should receive them shortly.</p>",
        )
        self.assertEquals([], mail.outbox)
