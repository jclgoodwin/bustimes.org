from django.test import TestCase
from ...models import Region, Operator, DataSource
from ..commands import import_live_guernsey


class SiriVMImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='GG')
        Operator.objects.create(id='guernsey', region_id='GG')
        now = '2018-08-06T22:41:15+01:00'
        cls.source = DataSource.objects.create(datetime=now)

    def test_handle(self):
        command = import_live_guernsey.Command()
        command.source = self.source

        item = {
            "id": 17,
            "label": "R",
            "html": "widget",
            "line": "/img/94.png",
            "name": "362_-_46893",
            "position": {"lat": 49.451431, "long": -2.541238}
        }

        command.handle_item(item, self.source.datetime)

        item['name'] = 'Dummy'
        command.handle_item(item, self.source.datetime)

        self.assertEquals(1, self.source.vehiclelocation_set.count())

        response = self.client.get('/operators/guernsey/vehicles')
        self.assertContains(response, '362 - 46893')

        # B-1GV
        item['name'] = '1965-35428'
        command.handle_item(item, self.source.datetime)
