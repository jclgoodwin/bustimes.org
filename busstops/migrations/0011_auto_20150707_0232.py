# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0010_service_stops'),
    ]

    operations = [
        migrations.AlterField(
            model_name='service',
            name='stops',
            field=models.ManyToManyField(to='busstops.StopPoint', editable=False),
        ),
    ]
