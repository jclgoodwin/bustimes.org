# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0021_auto_20151011_1313'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='date',
            field=models.DateField(default=datetime.datetime(1970, 1, 1, 0, 0)),
            preserve_default=False,
        ),
    ]
