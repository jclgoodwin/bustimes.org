from django.db import models
from django.urls import reverse


class Licence(models.Model):
    name = models.CharField(max_length=48)
    trading_name = models.CharField(max_length=48)
    traffic_area = models.CharField(max_length=1)
    licence_number = models.CharField(max_length=20, unique=True)
    discs = models.PositiveIntegerField()
    authorised_discs = models.PositiveIntegerField()

    def __str__(self):
        return self.licence_number

    def get_absolute_url(self):
        return reverse('licence_detail', args=(self.licence_number,))


class Registration(models.Model):
    licence = models.ForeignKey(Licence, models.CASCADE)
    registration_number = models.CharField(max_length=20, unique=True)
    service_number = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    start_point = models.CharField(max_length=255)
    finish_point = models.CharField(max_length=255)
    via = models.CharField(blank=True, max_length=255)
    subsidies_description = models.CharField(max_length=255)
    subsidies_details = models.CharField(max_length=255)
    licence_status = models.CharField(max_length=255)
    registration_status = models.CharField(max_length=255, db_index=True)
    traffic_area_office_covered_by_area = models.CharField(max_length=100)

    def __str__(self):
        string = '{} - {} - {}'.format(self.service_number, self.start_point, self.finish_point)
        if self.via:
            string = '{} via {}'.format(string, self.via)
        return string

    def get_absolute_url(self):
        return reverse('registration_detail', args=(self.registration_number,))


class Variation(models.Model):
    registration = models.ForeignKey(Registration, models.CASCADE)
    variation_number = models.PositiveIntegerField()
    granted_date = models.DateField()
    expiry_date = models.DateField()
    effective_date = models.DateField(null=True)
    date_received = models.DateField(null=True)
    end_date = models.DateField(null=True)
    service_type_other_details = models.TextField()
    registration_status = models.CharField(max_length=255)
    publication_text = models.TextField()
    service_type_description = models.CharField(max_length=255)
    short_notice = models.CharField(max_length=255)
    authority_description = models.CharField(max_length=255)

    class Meta():
        ordering = ('-variation_number',)
        unique_together = ('registration', 'variation_number')

    def __str__(self):
        return str(self.registration)

    def get_absolute_url(self):
        return reverse('registration_detail', args=(self.registration.registration_number,))
