# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Operator',
            fields=[
                ('id', models.CharField(max_length=10, serialize=False, primary_key=True)),
                ('short_name', models.CharField(max_length=48)),
                ('public_name', models.CharField(max_length=48)),
                ('reference_name', models.CharField(max_length=48)),
                ('license_name', models.CharField(max_length=48)),
                ('vehicle_mode', models.CharField(max_length=48)),
                ('parent', models.CharField(max_length=48)),
            ],
        ),
    ]
