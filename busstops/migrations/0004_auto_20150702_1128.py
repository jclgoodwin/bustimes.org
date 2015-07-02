# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0003_auto_20150702_1123'),
    ]

    operations = [
        migrations.AddField(
            model_name='operator',
            name='parent',
            field=models.CharField(default='', max_length=48),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='operator',
            name='vehicle_mode',
            field=models.CharField(default='Bus', max_length=48),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='operator',
            name='license_name',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='operator',
            name='public_name',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='operator',
            name='reference_name',
            field=models.CharField(max_length=100),
        ),
    ]
