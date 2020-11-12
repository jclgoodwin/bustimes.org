from django.db import models


class Currency(models.TextChoices):
    GBP = "GBP", "Pound Sterling"
    EUR = "EUR", "Euro"


class Price(models.Model):
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.GBP,
    )
    value = models.DecimalField(max_digits=5, decimal_places=2)  # maximum £999.99


class Tariff(models.Model):
    # dates =
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)


class UserProfile(models.Model):
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)
    proof_required = models.CharField(max_length=255, blank=True)
    discount_basis = models.CharField(max_length=255, blank=True)
    min_age = models.PositiveSmallIntegerField(null=True, blank=True)
    max_age = models.PositiveSmallIntegerField(null=True, blank=True)


class FareTable(models.Model):
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)
    user_profile = models.ForeignKey("UserProfile")


class FareZone(models.Model):
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    stops = models.ManyToManyField("busstops.StopPoint")

    def __str__(self):
        return self.name


class PriceGroup(models.Model):
    code = models.CharField(max_length=255)


class DistanceMatrixElement(models.Model):
    code = models.CharField(max_length=255)
    price_groups = models.ManyToManyField("PriceGroup")


class DistanceMatrixElementPrice(models.Model):
    distance_matrix_element = models.ForeignKey(DistanceMatrixElement)
    price_group = models.ForeignKey(PriceGroup)
