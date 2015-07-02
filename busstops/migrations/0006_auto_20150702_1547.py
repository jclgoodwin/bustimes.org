# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0005_auto_20150702_1533'),
    ]

    operations = [
        migrations.AlterField(
            model_name='serviceversion',
            name='description',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='serviceversion',
            name='stops',
            field=models.ManyToManyField(to='busstops.StopPoint', editable=False),
        ),
    ]
