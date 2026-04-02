from django.test import TestCase
from .urlise import urlise


class UrliseTest(TestCase):
    def test_national_express(self):
        self.assertEqual(
            urlise("https://www.nationalexpress.com/en/destinations/manchester"),
            '<a href="https://nationalexpress.prf.hn/click/camref:1011ljPYw/destination:https://www.nationalexpress.com/en/destinations/manchester" rel="nofollow">nationalexpress.com/en/destinations/manchester</a>',
        )

        self.assertEqual(
            urlise("http://www.nationalexpress.com"),
            '<a href="https://nationalexpress.prf.hn/click/camref:1011ljPYw" rel="nofollow">nationalexpress.com</a>',
        )

    def test_multiple_urls(self):
        self.assertEqual(
            urlise("https://example.com/ https://example.com/"),
            """<a href="https://example.com/" rel="nofollow">example.com</a> <a href="https://example.com/" rel="nofollow">example.com</a>""",
        )
