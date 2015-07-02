# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0002_operator'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='operator',
            name='parent',
        ),
        migrations.RemoveField(
            model_name='operator',
            name='vehicle_mode',
        ),
    ]
