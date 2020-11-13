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


class PriceGroup(models.Model):
    code = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=5, decimal_places=2)  # maximum £999.99

    def __str__(self):
        return self.code


class Tariff(models.Model):
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)

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


class Column(models.Model):
    table = models.ForeignKey(FareTable, models.CASCADE)
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(null=True)


class Row(models.Model):
    table = models.ForeignKey(FareTable, models.CASCADE)
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(null=True)


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


class DistanceMatrixElementPrice(models.Model):
    distance_matrix_element = models.ForeignKey(DistanceMatrixElement, models.CASCADE)
    price_group = models.ForeignKey(PriceGroup, models.CASCADE)
