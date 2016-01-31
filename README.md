# Bus Times

[![Build Status](https://travis-ci.org/jclgoodwin/bustimes.org.uk.svg?branch=master)](https://travis-ci.org/jclgoodwin/bustimes.org.uk)

## What's this?

It's [a thing about buses](https://bustimes.org.uk/).

## Installing

A database supported by GeoDjango is required – I use PostgreSQL with PostGIS.
I also use Nginx and uwsgi in production.

Here I've noted down some of the commands I used when manually provisioning a new server:

    apt-get install postgresql postgresql-contrib
    apt-get install libpq-dev python-dev gcc
    apt-get install python-virtualenv
    virtualenv env
    . env/bin/activate
    pip install django django-pipeline psycopg2
    apt-get install binutils libproj-dev gdal-bin
    apt-get install postgis
    apt-get install nginx uwsgi uwsgi-plugin-python

In an emergency, it's possible to run this on Heroku, but that's relatively expensive.

## Importing data

[`import.sh`](data/import.sh) will download data from various sources and run the necessary Django [management commands](busstops/management/commands) to import it.
When run repeatedly, it will only download and import the stuff that's changed.
It expects to be run from the [`data`](data) directory, and needs a username and password to import TNDS data.
