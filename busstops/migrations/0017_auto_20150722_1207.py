# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0016_auto_20150721_1641'),
    ]

    operations = [
        migrations.AlterField(
            model_name='locality',
            name='parent',
            field=models.ForeignKey(null=True, editable=False, help_text='', to='busstops.Locality'),
        ),
        migrations.AlterField(
            model_name='stoppoint',
            name='stop_area',
            field=models.ForeignKey(null=True, editable=False, help_text='', to='busstops.StopArea'),
        ),
    ]
