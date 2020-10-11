from django.db import models


class Currency(models.TextChoices):
    GBP = 'GBP', 'Pound Sterling'
    EUR = 'EUR', 'Euro'


class Price(models.Model):
    currency = models.CharField(max_length=24)
    value = models.DecimalField(max_digits=5, decimal_places=2)
    models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.GBP,
    )


class FareZone(models.Model):
    name = models.CharField(max_length=255)
    stops = models.ManyToManyField('busstops.StopPoint')

    def __str__(self):
        return self.name
