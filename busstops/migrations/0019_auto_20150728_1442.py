# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0018_auto_20150722_1444'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='serviceversion',
            name='line_name',
        ),
        migrations.RemoveField(
            model_name='serviceversion',
            name='mode',
        ),
        migrations.AddField(
            model_name='service',
            name='description',
            field=models.CharField(default='', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='service',
            name='line_name',
            field=models.CharField(default='', max_length=24),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='service',
            name='mode',
            field=models.CharField(default='', max_length=10),
            preserve_default=False,
        ),
    ]
