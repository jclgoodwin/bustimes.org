# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0002_auto_20150702_1240'),
    ]

    operations = [
        migrations.AddField(
            model_name='operator',
            name='region',
            field=models.ForeignKey(default='GB', to='busstops.Region'),
            preserve_default=False,
        ),
    ]
