# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0023_service_region'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='current',
            field=models.BooleanField(default=True),
        ),
    ]
