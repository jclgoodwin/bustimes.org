# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0009_remove_serviceversion_stops'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='stops',
            field=models.ManyToManyField(to='busstops.StopPoint'),
        ),
    ]
