#!/bin/bash

# Usage:
#
#     cd data
#     ./import.sh username password
#
# Where 'username' and 'password' are your username and password for the
# Traveline National Dataset FTP server

if [ `ps -e | grep -c import.sh` -gt 2 ]; then
    echo "An import appears to be running already"
    exit 0
fi

USERNAME=$1
PASSWORD=$2
REGIONS=(NCSD EA W EM Y NW S WM SW SE NE L) # roughly in ascending size order

function import_csv {
    # name of a zip archive:
    zip=$1
    # fragment of a Django management command name:
    cmd=$2
    # name of a CSV file contained in the zip archive:
    csv=$3

    tail -n +2 $csv > previous/$csv || touch previous/$csv
    unzip -oq $zip $csv
    diff -h previous/$csv $csv | grep '^> ' | sed 's/^> //' | ../../manage.py import_$cmd
}

mkdir -p NPTG/previous NaPTAN/previous TNDS
. ../env/bin/activate

cd NPTG
nptg_old=`ls -l nptgcsv.zip`
wget -qN http://81.17.70.199/nptg/snapshot/nptgcsv.zip
nptg_new=`ls -l nptgcsv.zip`

if [[ $nptg_old != $nptg_new ]]; then
    echo "NPTG"
    echo "  Changes found"
    echo "  Importing regions"
    import_csv nptgcsv.zip regions Regions.csv
    echo "  Importing areas"
    import_csv nptgcsv.zip areas AdminAreas.csv
    echo "  Importing districts"
    import_csv nptgcsv.zip districts Districts.csv
    echo "  Importing localities"
    import_csv nptgcsv.zip localities Localities.csv
    echo "  Importing locality hierarchy"
    import_csv nptgcsv.zip locality_hierarchy LocalityHierarchy.csv
    ../../manage.py update_index busstops.Locality --remove
fi

cd ../NaPTAN
naptan_old=`ls -l NaPTANcsv.zip`
wget -qN http://81.17.70.199/NaPTAN/snapshot/NaPTANcsv.zip
naptan_new=`ls -l NaPTANcsv.zip`

if [[ $nptg_old$naptan_old != $nptg_new$naptan_new ]]; then
    echo "NaPTAN"
    echo "  Changes found"
    echo "  Unzipping"
    (
    echo "  Stops"
    import_csv NaPTANcsv.zip stops Stops.csv
    ) &
    (
    echo "  Stop areas"
    import_csv NaPTANcsv.zip stop_areas StopAreas.csv
    ) &
    wait
    (
    echo "  Stops in area"
    import_csv NaPTANcsv.zip stops_in_area StopsInArea.csv
    echo "  Cleaning stops"
    ../../manage.py clean_stops
    ) &
fi

cd ..
noc_old=`ls -l NOC_DB.csv`
wget -qN http://mytraveline.info/NOC/NOC_DB.csv
wget -qN www.travelinedata.org.uk/noc/api/1.0/nocrecords.xml
noc_new=`ls -l NOC_DB.csv`
if [[ $noc_old != $noc_new ]]; then
    ../manage.py import_operators < NOC_DB.csv
    ../manage.py correct_operator_regions
    ../manage.py import_operator_contacts < nocrecords.xml
    ../manage.py import_scotch_operator_contacts < NOC_DB.csv
    ../manage.py update_index busstops.Operator --remove
fi

if [[ $USERNAME == '' || $PASSWORD == '' ]]; then
   echo 'TNDS username and/or password not supplied :('
   exit 1
fi

cd TNDS
for region in ${REGIONS[@]}; do
    region_old=`ls -l $region.zip`
    wget -qN --user=$USERNAME --password=$PASSWORD ftp://ftp.tnds.basemap.co.uk/$region.zip
    region_new=`ls -l $region.zip`
    if [[ $nptg_old$naptan_old$region_old != $nptg_new$naptan_new$region_new ]]; then
        updated_services=1
        ../../manage.py import_services $region.zip
        unzip -oq $region.zip -d $region
        find $region -type f -mtime +2 -delete
        unzip -oq $region.zip -d $region
        find $region -type f -empty -delete
        ../corrections.sh
    fi
done
[ $updated_services ] && ../../manage.py update_index --remove
