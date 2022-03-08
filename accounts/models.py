from django.db import models

from django.contrib.auth.models import AbstractUser, UserManager
from django.urls import reverse


class CustomUserManager(UserManager):
    def get_by_natural_key(self, username):
        return self.get(email__iexact=username)


class OperatorUser(models.Model):
    operator = models.ForeignKey('busstops.Operator', models.CASCADE)
    user = models.ForeignKey('User', models.CASCADE)
    staff = models.BooleanField(default=False)


class User(AbstractUser):
    email = models.EmailField(unique=True, verbose_name='email address')
    trusted = models.BooleanField(null=True)
    operators = models.ManyToManyField('busstops.Operator', blank=True, through=OperatorUser)

    objects = CustomUserManager()

    REQUIRED_FIELDS = []
    USERNAME_FIELD = 'email'

    def get_absolute_url(self):
        return reverse('user_detail', args=(self.id,))

    def __str__(self):
        if '@' not in self.username:
            return self.username
        return f'{self.id}'
