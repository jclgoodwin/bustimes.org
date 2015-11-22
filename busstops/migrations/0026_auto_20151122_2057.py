# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0025_auto_20151117_2011'),
    ]

    operations = [
        migrations.AlterField(
            model_name='operator',
            name='parent',
            field=models.CharField(max_length=48, blank=True),
        ),
        migrations.AlterField(
            model_name='operator',
            name='vehicle_mode',
            field=models.CharField(max_length=48, blank=True),
        ),
    ]
