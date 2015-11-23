# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0026_auto_20151122_2057'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stoppoint',
            name='active',
            field=models.BooleanField(db_index=True),
        ),
    ]
