#!/bin/bash

# Usage:
#
#     poetry run ./import.sh username password
#
# Where 'username' and 'password' are your username and password for the
# Traveline National Dataset FTP server


# create lockfile
# I think it's important that this goes before the `trap`
mkdir /var/lock/bustimes-import || {
    echo "An import appears to be running already"
    exit 1
}

function finish {
    # remove lockfile
    rmdir /var/lock/bustimes-import 2> /dev/null
}
trap finish EXIT SIGINT SIGTERM

USERNAME=$1
PASSWORD=$2


./manage.py nptg
./manage.py naptan_new


cd data

ie_nptg_old=$(shasum NPTG_final.xml)
wget -qN https://www.transportforireland.ie/transitData/NPTG_final.xml
ie_nptg_new=$(shasum NPTG_final.xml)

cd ..

if [[ "$ie_nptg_old" != "$ie_nptg_new" ]]; then
    echo "Irish NPTG"
    ./manage.py import_ie_nptg data/NPTG_final.xml
fi


cd data

noc_old=$(ls -l NOC_DB.csv)
wget -qN https://mytraveline.info/NOC/NOC_DB.csv
noc_new=$(ls -l NOC_DB.csv)

cd ..

if [[ $noc_old != $noc_new ]]; then
    wget -O nocrecords.xml www.travelinedata.org.uk/noc/api/1.0/nocrecords.xml
    ./manage.py import_operators < data/NOC_DB.csv
    ./manage.py import_operator_contacts < data/nocrecords.xml
    ./manage.py correct_operators
fi

if [[ $USERNAME == '' || $PASSWORD == '' ]]; then
   echo 'TNDS username and/or password not supplied :('
   exit 1
fi

./manage.py import_tnds "$USERNAME" "$PASSWORD"

./manage.py import_gtfs

finish
