# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0020_service_net'),
    ]

    operations = [
        migrations.AlterField(
            model_name='service',
            name='operator',
            field=models.ManyToManyField(to='busstops.Operator', blank=True),
        ),
    ]
