# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0008_auto_20150702_1824'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='serviceversion',
            name='stops',
        ),
    ]
