# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0015_auto_20150721_1517'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='operator',
            name='license_name',
        ),
        migrations.RemoveField(
            model_name='operator',
            name='public_name',
        ),
        migrations.RemoveField(
            model_name='operator',
            name='reference_name',
        ),
        migrations.RemoveField(
            model_name='operator',
            name='short_name',
        ),
        migrations.AddField(
            model_name='operator',
            name='name',
            field=models.CharField(default='', max_length=100),
            preserve_default=False,
        ),
    ]
