#!/bin/bash

# Usage:
#
#     poetry run ./import.sh username password
#
# Where 'username' and 'password' are your username and password for the
# Traveline National Dataset FTP server


# I think it's important that this goes before the `trap`
mkdir /var/lock/bustimes-import || {
    echo "An import appears to be running already"
    exit 1
}

function finish {
    rmdir /var/lock/bustimes-import 2> /dev/null
}
trap finish EXIT SIGINT SIGTERM

USERNAME=$1
PASSWORD=$2

function import_csv {
    # name of a zip archive:
    zip=$1
    # fragment of a Django management command name:
    cmd=$2
    # name of a CSV file contained in the zip archive:
    csv=$3

    cd data/NPTG
    unzip -oq "$zip" "$csv"
    cd ../..
    ./manage.py "import_$cmd" < "data/NPTG/$csv"
}

mkdir -p data/NPTG/previous data/variations

cd data/NPTG

nptg_old=$(shasum nptg.ashx\?format=csv)
wget -qN https://naptan.app.dft.gov.uk/datarequest/nptg.ashx?format=csv
nptg_new=$(shasum nptg.ashx\?format=csv)

cd ../..


if [[ $nptg_old != "$nptg_new" ]]; then
    echo "NPTG"
    echo "  Importing regions"
    import_csv nptg.ashx\?format=csv regions Regions.csv
    echo "  Importing areas"
    import_csv nptg.ashx\?format=csv areas AdminAreas.csv
    echo "  Importing districts"
    import_csv nptg.ashx\?format=csv districts Districts.csv
    echo "  Importing localities"
    import_csv nptg.ashx\?format=csv localities Localities.csv
    echo "  Importing locality hierarchy"
    import_csv nptg.ashx\?format=csv adjacent_localities AdjacentLocality.csv
    echo "  Importing adjacent localities"
    import_csv nptg.ashx\?format=csv locality_hierarchy LocalityHierarchy.csv
fi

cd data


ie_nptg_old=$(shasum NPTG_final.xml)
wget -qN https://www.transportforireland.ie/transitData/NPTG_final.xml
ie_nptg_new=$(shasum NPTG_final.xml)

cd ..

if [[ "$ie_nptg_old" != "$ie_nptg_new" ]]; then
    echo "Irish NPTG"
    ./manage.py import_ie_nptg data/NPTG_final.xml
fi


./manage.py naptan_new


noc_old=$(ls -l NOC_DB.csv)
wget -qN https://mytraveline.info/NOC/NOC_DB.csv
noc_new=$(ls -l NOC_DB.csv)
if [[ $noc_old != $noc_new ]]; then
    wget www.travelinedata.org.uk/noc/api/1.0/nocrecords.xml
    ./manage.py import_operators < NOC_DB.csv
    ./manage.py import_operator_contacts < nocrecords.xml
    ./manage.py correct_operators
fi

if [[ $USERNAME == '' || $PASSWORD == '' ]]; then
   echo 'TNDS username and/or password not supplied :('
   exit 1
fi

./manage.py import_tnds "$USERNAME" "$PASSWORD"

./manage.py import_gtfs

finish
