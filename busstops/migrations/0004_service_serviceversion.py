# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0003_operator_region'),
    ]

    operations = [
        migrations.CreateModel(
            name='Service',
            fields=[
                ('service_code', models.CharField(max_length=12, serialize=False, primary_key=True)),
                ('operator', models.ForeignKey(to='busstops.Operator')),
            ],
        ),
        migrations.CreateModel(
            name='ServiceVersion',
            fields=[
                ('name', models.CharField(max_length=12, serialize=False, primary_key=True)),
                ('line_name', models.CharField(max_length=10)),
                ('mode', models.CharField(max_length=10)),
                ('description', models.CharField(max_length=48)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(null=True)),
                ('service', models.ForeignKey(to='busstops.Service')),
                ('stops', models.ManyToManyField(to='busstops.StopPoint')),
            ],
        ),
    ]
