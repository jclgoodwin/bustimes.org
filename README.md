[![Python application](https://github.com/jclgoodwin/bustimes.org/workflows/Python%20application/badge.svg)](https://github.com/jclgoodwin/bustimes.org/actions)

[Coverage](https://bustimes-coverage.ams3.digitaloceanspaces.com/index.html)

## What's this?

Source code for [the website bustimes](https://bustimes.org/).

It's a magnificent monolithic Django app that's evolved over time (since 2015). The structure doesn't make complete sense:

app      | concern
---------|------------
buses    | contains the site settings.py
busstops | bus stops - but also operating companies, places, and routes 🤯 and all the site CSS and JavaScript
bustimes | getting timetable data out of various formats (GTFS, TransXChange, ATCO-CIF) and into a database and doing stuff therewith 
vehicles | tracking buses's locations and showing them on a map
departures | listing the "next departues" at a bus stop – from a timetable and/or predicted by an API
disruptions | information about like roadworks, diversions and stuff
vosa     | the Great Britain Traffic Commissioners' bus service registration data. VOSA is the name of a defunct UK government agency. 

This documentation is incomplete and out of date. And that's OK (?) because I don't expect anyone to need to follow it. I will try to document some things for my own reference.

## Installing

I'm using Python 3.8 and I don't know if any lower versions still work.
Use [Pipenv](https://docs.pipenv.org/en/latest/) to install the Python dependencies (Django, etc):

    pipenv --python 3.8
    pipenv install --dev

There are also some JavaScript dependencies:

    npm install

## Importing data

### Static data (stops, timetables, etc)

[`import.sh`](data/import.sh) will download data from various [sources](https://bustimes.org.uk/data) and run the necessary Django [management commands](busstops/management/commands) to import it.
When run repeatedly, it will only download and import the stuff that's changed.
It expects to be run from the [`data`](data) directory.
It needs a username and password for the Traveline National Dataset step.

### Live data

Some "live" data – departure times at stops, and vehicle locations – is/are fetched as and when a user accesses a page.

For the rest, there are some Django management commands that need to be run indefinitely in the background.
These update [the big map of bus locations](https://bustimes.org/map), etc.
