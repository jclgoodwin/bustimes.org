from django.db import models
from django.urls import reverse


# class Currency(models.TextChoices):
#     GBP = "GBP", "Pound Sterling"
#     EUR = "EUR", "Euro"


# currency = models.CharField(
#     max_length=3,
#     choices=Currency.choices,
#     default=Currency.GBP,
# )


class DataSet(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField(blank=True)

    def __str__(self):
        return self.name


class PriceGroup(models.Model):
    code = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=5, decimal_places=2)  # maximum £999.99

    def __str__(self):
        return self.code


class TimeInterval(models.Model):
    code = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)


class TimeIntervalPrice(models.Model):
    code = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=5, decimal_places=2)  # maximum £999.99
    time_interval = models.ForeignKey(TimeInterval, models.CASCADE)


class SalesOfferPackage(models.Model):
    code = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)


class Tariff(models.Model):
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    services = models.ManyToManyField('busstops.Service')
    operators = models.ManyToManyField('busstops.Operator')
    source = models.ForeignKey(DataSet, models.CASCADE)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('tariff_detail', args=(self.id,))


class UserProfile(models.Model):
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)
    proof_required = models.CharField(max_length=255, blank=True)
    discount_basis = models.CharField(max_length=255, blank=True)
    min_age = models.PositiveSmallIntegerField(null=True, blank=True)
    max_age = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return self.name


class FareTable(models.Model):
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)
    user_profile = models.ForeignKey(UserProfile, models.CASCADE)
    tariff = models.ForeignKey(Tariff, models.CASCADE)

    def __str__(self):
        return self.name


class FareZone(models.Model):
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    stops = models.ManyToManyField("busstops.StopPoint")

    def __str__(self):
        return self.name


class DistanceMatrixElement(models.Model):
    code = models.CharField(max_length=255)
    price_group = models.ForeignKey(PriceGroup, models.CASCADE)
    start_zone = models.ForeignKey(FareZone, models.CASCADE, related_name='starting')
    end_zone = models.ForeignKey(FareZone, models.CASCADE, related_name='ending')
    tariff = models.ForeignKey(Tariff, models.CASCADE)

    def __str__(self):
        return self.code


class Column(models.Model):
    table = models.ForeignKey(FareTable, models.CASCADE)
    code = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return self.name.replace("/", "/\u200B")


class Row(models.Model):
    table = models.ForeignKey(FareTable, models.CASCADE)
    code = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(null=True, blank=True)


class Cell(models.Model):
    column = models.ForeignKey(Column, models.CASCADE)
    row = models.ForeignKey(Row, models.CASCADE)
    distance_matrix_element = models.ForeignKey(DistanceMatrixElement, models.CASCADE, null=True)
    price_group = models.ForeignKey(PriceGroup, models.CASCADE, null=True)
    time_interval_price = models.ForeignKey(TimeIntervalPrice, models.CASCADE, null=True)
