# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0013_auto_20150712_1041'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stoparea',
            name='parent',
            field=models.ForeignKey(editable=False, to='busstops.StopArea', null=True),
        ),
        migrations.AlterField(
            model_name='stoparea',
            name='stop_area_type',
            field=models.CharField(max_length=4, choices=[(b'GPBS', b'on-street pair'), (b'GCLS', b'on-street cluster'), (b'GAIR', b'airport building'), (b'GBCS', b'bus/coach station'), (b'GFTD', b'ferry terminal/dock'), (b'GTMU', b'tram/metro station'), (b'GRLS', b'rail station'), (b'GCCH', b'coach service coverage')]),
        ),
    ]
