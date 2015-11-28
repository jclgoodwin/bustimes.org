# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0029_auto_20151125_2119'),
    ]

    operations = [
        migrations.AddField(
            model_name='locality',
            name='adjancent',
            field=models.ManyToManyField(related_name='neighbour', to='busstops.Locality'),
        ),
        migrations.AlterField(
            model_name='service',
            name='description',
            field=models.CharField(max_length=128),
        ),
    ]
