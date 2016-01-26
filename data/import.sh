#!/bin/bash

# Usage:
#
#     cd data
#     ./import.sh username password
#
# Where 'username' and 'password' are your username and password for the
# Traveline National Dataset FTP server

USERNAME=$1
PASSWORD=$2
REGIONS=(EA EM L NE NW S SE SW W WM Y NCSD)

# set $md5 to the name of the system's md5 hash command ('md5' or 'md5sum')
md5=$(which md5)
if [[ ! "${md5}" ]]; then
    md5=$(which md5sum)
    if [[ ! "${md5}" ]]; then
        echo "Neither md5 nor md5sum found :("
        exit 1
    fi
fi

function import_csv {
    cmd=$1
    filename=$2

    tail -n +2 $filename > previous/$filename || touch previous/$filename
    diff previous/$filename $filename | grep '^> ' | sed 's/^> //' | $cmd
}

mkdir -p NPTG/previous NaPTAN/previous TNDS
. ../env/bin/activate

cd NPTG
nptg_md5_old=`$md5 nptgcsv.zip`
wget -qN http://81.17.70.199/nptg/snapshot/nptgcsv.zip
nptg_md5_new=`$md5 nptgcsv.zip`

if [[ $nptg_md5_old != $nptg_md5_new ]]; then
    echo "NPTG"
    echo "  Changes found"
    echo "  Unzipping"
    unzip -oq nptgcsv.zip
    echo "  Importing regions"
    import_csv "../../manage.py import_regions" Regions.csv
    echo "  Importing areas"
    import_csv "../../manage.py import_areas" AdminAreas.csv
    echo "  Importing districts"
    import_csv "../../manage.py import_districts" Districts.csv
    echo "  Importing localities"
    import_csv "../../manage.py import_localities" Localities.csv
    echo "  Importing locality hierarchy"
    import_csv "../../manage.py import_locality_hierarchy" LocalityHierarchy.csv
fi

cd ../NaPTAN
naptan_md5_old=`$md5 NaPTANcsv.zip`
wget -qN http://81.17.70.199/NaPTAN/snapshot/NaPTANcsv.zip
naptan_md5_new=`$md5 NaPTANcsv.zip`

if [[ $nptg_md5_old != $nptg_md5_new || $naptan_md5_old != $naptan_md5_new ]]; then
    echo "NaPTAN"
    echo "  Changes found"
    echo "  Unzipping"
    unzip -oq NaPTANcsv.zip
    (
    echo "  Stops"
    import_csv "../../manage.py import_stops" Stops.csv
    echo "  Cleaning stops"
    ../../manage.py clean_stops
    ) &
    (
    echo "  Stop areas"
    import_csv "../../manage.py import_stop_areas" StopAreas.csv
    ) &
    wait
    echo "  Stops in area"
    import_csv "../../manage.py import_stops_in_area" StopsInArea.csv
fi

cd ..
noc_md5_old=`$md5 NOC_DB.csv`
wget -qN http://mytraveline.info/NOC/NOC_DB.csv
noc_md5_new=`$md5 NOC_DB.csv`
if [[ $noc_md5_old != $noc_md5_new ]]; then
    ../manage.py import_operators < NOC_DB.csv
fi

if [[ $USERNAME == '' || $PASSWORD == '' ]]; then
   echo 'TNDS username and/or password not supplied :('
   exit 1
fi

cd TNDS
workers=0
for region in ${REGIONS[@]}; do
    region_md5_old=`$md5 $region.zip`
    wget -qN --user=$USERNAME --password=$PASSWORD ftp://ftp.tnds.basemap.co.uk/$region.zip
    region_md5_new=`$md5 $region.zip`
    if [[ $nptg_md5_old != $nptg_md5_new || $naptan_md5_old != $naptan_md5_new || $region_md5_old != $region_md5_new ]]; then
        workers=$(($workers + 1))
        echo $region
        (
        ../../manage.py import_services $region.zip
        ) &
        if [[ $workers -ge 2 ]]; then
            wait
            workers=0
        fi
    fi
done
wait
