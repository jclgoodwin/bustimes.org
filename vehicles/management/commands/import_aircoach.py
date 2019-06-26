from multigtfs.models import Route
from .import_nx import sleep, RequestException, Command as NatExpCommand


class Command(NatExpCommand):
    source_name = 'Aircoach'
    operators = ['663']

    def get_items(self):
        url = 'https://tracker.aircoach.ie/api/eta/routes/{}/{}'

        for route in Route.objects.filter(agency__name='Aircoach'):
            for direction in 'OI':
                try:
                    res = self.session.get(url.format(route.short_name.replace('-x', 'X'), direction), timeout=5)
                except RequestException as e:
                    print(e)
                    continue
                if not res.ok:
                    print(res)
                    continue
                if direction != res.json()['dir']:
                    print(res.url)
                for item in res.json()['services']:
                    if item['live']:
                        item['route'] = item['route'].replace('X', '-x')
                        yield(item)
                sleep(5)
