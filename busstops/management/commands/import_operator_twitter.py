from urllib.parse import urlparse
from requests.exceptions import RequestException
from requests_html import HTMLSession
from django.core.management.base import BaseCommand
from ...models import Operator


class Command(BaseCommand):
    "We're uninterested in these - we're only interested in actual Twitter account links"
    shit_paths = ('/search', '/intent', '/message', '/share')

    @classmethod
    def get_from_link(cls, link):
        if 'twitter.com' not in link:
            return
        path = urlparse(link).path
        if len(path) > 2 and path[0] == '/' and path.count('/') == 1:
            for shit_path in cls.shit_paths:
                if path.startswith(shit_path):
                    return
            path = path[1:]
            if path[0] == '@':
                path = path[1:]
            return path

    def handle(cls, *args, **kwargs):
        session = HTMLSession()

        for operator in Operator.objects.filter(service__current=True, twitter='').exclude(url='').distinct():
            try:
                r = session.get(operator.url, timeout=10)
            except RequestException:
                operator.url = ''
                operator.save()
                continue
            for link in r.html.links:
                twitter = cls.get_from_link(link)
                if twitter:
                    operator.twitter = twitter
                    operator.save()
                    break
