[![Python application](https://github.com/jclgoodwin/bustimes.org/workflows/Python%20application/badge.svg)](https://github.com/jclgoodwin/bustimes.org/actions)

[Coverage](https://bustimes-coverage.ams3.digitaloceanspaces.com/index.html)

## What's this?

Source code for [the website bustimes.org](https://bustimes.org/).

It's a magnificent monolithic Django app that's evolved over time (since 2015). The structure doesn't make complete sense:

app      | concern
---------|------------
buses    | contains the site settings.py
busstops | bus stops - but also operating companies, places, and routes 🤯 and all the site CSS and JavaScript
bustimes | getting timetable data out of various formats (GTFS, TransXChange, ATCO-CIF) and into a database and doing stuff therewith 
departures | listing the "next departures" at a bus stop – from a timetable and/or predicted by an API
disruptions | information about like roadworks, diversions and stuff
fares    | fares
vehicles | tracking buses' locations and showing them on a map, and pointless details about vehicles' colours and features
vosa     | the Great Britain Traffic Commissioners' bus service registration data. VOSA is the name of a defunct UK government agency. 

This documentation is incomplete and out of date. And that's OK (?) because I don't expect anyone to need to follow it. I will try to document some things for my own reference.

## Installing

### Using Docker

You need Docker installed with docker-compose 1.27.0+. Then you can start the whole environment:

```
docker-compose up
```

### Using local install

These need to be available:

- Python 3.9+
- [Poetry](https://python-poetry.org/) to install necessary Python packages (Django, etc)
- PostgreSQL with PostGIS
    - On my Macintosh computer I use [Postgres.app](https://postgresapp.com/)
- `npm` to install some front end JavaScript things
- Redis 6.2+
- [GDAL](https://gdal.org/)

Some environment variables need to be set.
Many of them control settings in [buses/settings.py](buses/settings.py).

```
DEBUG=1
SECRET_KEY=f
ALLOWED_HOSTS=localhost macbook-pro-16.local
#PYTHONWARNINGS=all
PGHOST=localhost
PGUSER=postgres
PGPASSWORD=password
#PGPORT=
#DB_NAME=
CELERY_BROKER_URL=redis://localhost:6379
#AWS_ACCESS_KEY_ID=
#AWS_SECRET_ACCESS_KEY=
```

Then run, preferably in a virtual environment, those commands:

```
npm install
make build-static
poetry install
poetry run ./manage.py migrate
poetry run ./manage.py runserver 0.0.0.0:8000 
```

[.github/workflows/pythonapp.yml](.github/workflows/pythonapp.yml) sort of documents the process of installing dependencies and running tests.

## Importing data

### Static data (stops, timetables, etc)

	cd data
	pipenv run ./import.sh

will download *some* data from various [sources](https://bustimes.org/data) and run the necessary Django [management commands](busstops/management/commands) to import it, in a sensible order (place names, then stops, then timetables).
When run repeatedly, it will only download and import the stuff that's changed.
It needs a username and password for the Traveline National Dataset step.

But then there are further management commands for getting further data from further places like the Bus Open Data Service.

### Live data

Some "live" data – departure times at stops, and vehicle locations – is/are fetched as and when a user accesses a page.

For the rest, there are some Django management commands that need to be run indefinitely in the background.
These update [the big map of bus locations](https://bustimes.org/map), etc.
