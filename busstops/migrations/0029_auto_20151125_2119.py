# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0028_auto_20151123_1853'),
    ]

    operations = [
        migrations.AlterField(
            model_name='operator',
            name='name',
            field=models.CharField(max_length=100, db_index=True),
        ),
    ]
