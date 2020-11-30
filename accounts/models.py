from django.db.models.fields import EmailField, BooleanField
from django.contrib.auth.models import AbstractUser, UserManager
from django.urls import reverse


class CustomUserManager(UserManager):
    def get_by_natural_key(self, username):
        print(username)
        return self.get(email__iexact=username)


class User(AbstractUser):
    email = EmailField(unique=True, verbose_name='email address')
    trusted = BooleanField(null=True)

    objects = CustomUserManager()

    REQUIRED_FIELDS = []
    USERNAME_FIELD = 'email'

    def get_absolute_url(self):
        return reverse('user_detail', args=(self.id,))

    def __str__(self):
        if self.is_staff:
            return self.username
        return f'{self.id}'
