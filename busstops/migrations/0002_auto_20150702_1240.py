# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0001_squashed_0004_auto_20150702_1128'),
    ]

    operations = [
        migrations.AlterField(
            model_name='operator',
            name='parent',
            field=models.CharField(max_length=48),
        ),
        migrations.AlterField(
            model_name='operator',
            name='vehicle_mode',
            field=models.CharField(max_length=48),
        ),
    ]
