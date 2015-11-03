# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0022_service_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='region',
            field=models.ForeignKey(default='GB', to='busstops.Region'),
            preserve_default=False,
        ),
    ]
