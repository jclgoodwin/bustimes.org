from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.test import TestCase

from .models import Situation, ValidityPeriod


class DisruptionsTest(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        source = Situation.source.field.remote_field.model.objects.create(
            name="Test", url="http://example.com"
        )
        cls.situation = Situation.objects.create(
            source=source,
            summary="A pigeon got in the cab and bit the driver",
            publication_window=DateTimeTZRange(
                "2021-05-10T09:00:00Z", "2021-05-10T10:00:00Z", "[]"
            ),
        )

    def test_validity_periods_daily(self):
        self.assertEqual(self.situation.list_validity_periods(), [])
        ValidityPeriod.objects.bulk_create(
            [
                ValidityPeriod(
                    situation=self.situation,
                    period=DateTimeTZRange(
                        "2021-05-10T09:00:00Z", "2021-05-10T10:00:00Z", "[]"
                    ),
                ),
                ValidityPeriod(
                    situation=self.situation,
                    period=DateTimeTZRange(
                        "2021-05-11T09:00:00Z", "2021-05-11T10:00:00Z", "[]"
                    ),
                ),
            ]
        )
        self.assertEqual(
            self.situation.list_validity_periods(),
            [
                "10:00\u2009\u2013\u200911:00,\nMonday 10\u2009\u2013\u2009Tuesday 11 May 2021"
            ],
        )

    def test_validity_periods_nightly(self):
        self.assertEqual(self.situation.list_validity_periods(), [])
        ValidityPeriod.objects.bulk_create(
            [
                ValidityPeriod(
                    situation=self.situation,
                    period=DateTimeTZRange(
                        "2021-05-10T20:00:00Z", "2021-05-11T06:00:00Z", "[]"
                    ),
                ),
                ValidityPeriod(
                    situation=self.situation,
                    period=DateTimeTZRange(
                        "2021-05-11T20:00:00Z", "2021-05-12T06:00:00Z", "[]"
                    ),
                ),
            ]
        )
        self.assertEqual(
            self.situation.list_validity_periods(),
            [
                "21:00\u2009\u2013\u200907:00,\nMonday 10\u2009\u2013\u2009Wednesday 12 May 2021"
            ],
        )
