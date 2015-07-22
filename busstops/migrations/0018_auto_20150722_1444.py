# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0017_auto_20150722_1207'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='service',
            name='operator',
        ),
        migrations.AddField(
            model_name='service',
            name='operator',
            field=models.ManyToManyField(to='busstops.Operator'),
        ),
        migrations.AlterField(
            model_name='serviceversion',
            name='line_name',
            field=models.CharField(max_length=24),
        ),
    ]
