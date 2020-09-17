from django.test import TestCase
from django.core import mail
from .models import User


class RegistrationTest(TestCase):
    def test_registration(self):
        with self.assertNumQueries(2):
            response = self.client.post('/accounts/register/', {
                'email': 'rufus@herring.pizza',
            })
        self.assertContains(response, 'Check your email (rufus@herring.pizza')
        self.assertEquals('bustimes.org account', mail.outbox[0].subject)
        self.assertIn('a bustimes.org account', mail.outbox[0].body)

        user = User.objects.get()
        self.assertEqual(user.username, 'rufus@herring.pizza')
        self.assertEqual(user.email, 'rufus@herring.pizza')
