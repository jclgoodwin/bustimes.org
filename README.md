# Bus Times

[![Build Status](https://travis-ci.org/jclgoodwin/bustimes.org.svg?branch=master)](https://travis-ci.org/jclgoodwin/bustimes.org)
[![Coverage Status](https://coveralls.io/repos/github/jclgoodwin/bustimes.org/badge.svg?branch=master)](https://coveralls.io/github/jclgoodwin/bustimes.org?branch=master)

## What's this?

It's [a thing about buses](https://bustimes.org.uk/).

## Importing data

[`import.sh`](data/import.sh) will download data from various [sources](https://bustimes.org.uk/data) and run the necessary Django [management commands](busstops/management/commands) to import it.
When run repeatedly, it will only download and import the stuff that's changed.
It expects to be run from the [`data`](data) directory, and needs a username and password to import TNDS data.
