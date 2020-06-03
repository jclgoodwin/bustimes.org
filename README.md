# Bus Times

![Python application](https://github.com/jclgoodwin/bustimes.org/workflows/Python%20application/badge.svg)

## What's this?

It's [a thing about buses](https://bustimes.org/).

## Installing

Python 3.6 or newer is required. Use [Pipenv](https://docs.pipenv.org/en/latest/) to install the Python dependencies (Django, etc):

    pipenv --python 3.6
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
These update [the big map of bus locations](https://bustimes.org/vehicles), etc.
