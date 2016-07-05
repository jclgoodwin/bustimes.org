"""Tests for the buses app
"""
from django.test import TestCase, override_settings
from django.core import mail
from .utils import minify


class UtilsTests(TestCase):
    """Tests for the buses.utils module
    """
    def test_minify(self):
        """Test that the minify function minifies (while preserving some characters) as expected
        """
        self.assertEqual(minify("""
                   \n
            <marquee>
                {% if foo %}
     
                    {% if bar %}
                        <strong>Golf sale</strong>  \n
                    {% endif %}
                {% endif %}
            </marquee>
            """), """
<marquee>
{% if foo %}{% if bar %}<strong>Golf sale</strong>  \n{% endif %}{% endif %}</marquee>
""")


class BrokenLinkEmailsMiddlewareTests(TestCase):
    """Tests for BrokenLinkEmailsMiddleware
    """
    @override_settings(DEBUG=False)
    def test_not_found(self):
        """If a 404 error happens with a referrer when DEBUG=True
        it should send an email with the correct IP address in the body
        """
        with self.modify_settings(
            MIDDLEWARE_CLASSES={
                'append': 'buses.middleware.BrokenLinkEmailsMiddleware'
            }
        ):
            self.assertEqual(mail.outbox, [])
            response = self.client.get(
                '/services/1-45-A-y08-9',
                HTTP_X_FORWARDED_FOR='198.51.100.0, 203.0.113.0',
                HTTP_REFERER='https://bustimes.org.uk'
            )
            self.assertEqual(response.status_code, 404)
            self.assertEqual(mail.outbox[0].subject, '[Django] Broken link on testserver')
            self.assertEqual(mail.outbox[0].body, """Referrer: https://bustimes.org.uk
Requested URL: /services/1-45-A-y08-9
User agent: <none>
IP address: 198.51.100.0
""")
