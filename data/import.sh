#!/bin/bash

# Usage:
#
#     cd data
#     ./import.sh username password
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

    tail -n +2 "$csv" > "previous/$csv"
    first=$? # 1 if previous command failed ($csv doesn't exist yet), 0 otherwise
    unzip -oq "$zip" "$csv"
    if [[ $first == "0" ]]; then
        diff -h "previous/$csv" "$csv" | grep '^> ' | sed 's/^> //' | ../../manage.py "import_$cmd"
    else
        ../../manage.py "import_$cmd" < "$csv"
    fi
}

mkdir -p NPTG/previous NaPTAN TNDS variations

cd NPTG
nptg_old=$(shasum nptg.ashx\?format=csv)
wget -qN http://naptan.app.dft.gov.uk/datarequest/nptg.ashx?format=csv
nptg_new=$(shasum nptg.ashx\?format=csv)

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


cd ..

# Translink Metro
metro_old=$(shasum metro-and-glider.zip)
wget -qN https://www.opendatani.gov.uk/dataset/6d9677cf-8d03-4851-985c-16f73f7dd5fb/resource/153a47c3-59b1-404f-8ec6-e5230cc4377d/download/metro-and-glider.zip
metro_new=$(shasum metro-and-glider.zip)
if [[ "$metro_old" != "$metro_new" ]]; then
    ../manage.py import_atco_cif metro-and-glider.zip
fi

# Ulsterbus
ulb_old=$(shasum ulb.zip)
wget -qN https://www.opendatani.gov.uk/dataset/c1acee5b-a400-46bd-a795-9bf7637ff879/resource/291cbb54-7bb3-4df7-8599-0c8f49a20be6/download/ulb.zip
ulb_new=$(shasum ulb.zip)
if [[ "$ulb_old" != "$ulb_new" ]]; then
    ../manage.py import_atco_cif ulb.zip
fi



ie_nptg_old=$(shasum NPTG_final.xml)
wget -qN https://www.transportforireland.ie/transitData/NPTG_final.xml
ie_nptg_new=$(shasum NPTG_final.xml)
if [[ "$ie_nptg_old" != "$ie_nptg_new" ]]; then
    echo "Irish NPTG"
    ../manage.py import_ie_nptg NPTG_final.xml
fi



cd NaPTAN
naptan_old=$(shasum naptan.zip)
../../manage.py update_naptan
naptan_new=$(shasum naptan.zip)

if [[ "$naptan_old" != "$naptan_new" ]]; then
    echo "NaPTAN"
    unzip -oq naptan.zip
fi

if compgen -G "*csv.zip" > /dev/null; then
    for file in *csv.zip; do
        unzip -oq "$file" Stops.csv StopAreas.csv StopsInArea.csv
        echo " $file"
        echo "  Stops"
        tr -d '\000' < Stops.csv | ../../manage.py import_stops && rm Stops.csv
        ../../manage.py correct_stops
        echo "  Stop areas"
        tr -d '\000' < StopAreas.csv | ../../manage.py import_stop_areas && rm StopAreas.csv
        echo "  Stops in area"
        tr -d '\000' < StopsInArea.csv | ../../manage.py import_stops_in_area || continue && rm StopsInArea.csv
        rm "$file"
    done
elif [ -f Stops.csv ]; then
    echo "  Stops"
    tr -d '\000' < Stops.csv | ../../manage.py import_stops && rm Stops.csv
    echo "  Stop areas"
    tr -d '\000' < StopAreas.csv | ../../manage.py import_stop_areas && rm StopAreas.csv
    echo "  Stops in area"
    tr -d '\000' < StopsInArea.csv | ../../manage.py import_stops_in_area && rm StopsInArea.csv
    echo "  Stops in area"
    tr -d '\000' < CoachReferences.csv | ../../manage.py import_coach_references && rm CoachReferences.csv
fi


cd ..

noc_old=$(ls -l NOC_DB.csv)
wget -qN http://mytraveline.info/NOC/NOC_DB.csv
noc_new=$(ls -l NOC_DB.csv)
if [[ $noc_old != $noc_new ]]; then
    wget -qN www.travelinedata.org.uk/noc/api/1.0/nocrecords.xml
    ../manage.py import_operators < NOC_DB.csv
    ../manage.py import_operator_contacts < nocrecords.xml
    ../manage.py correct_operators
fi

cd ..

if [[ $USERNAME == '' || $PASSWORD == '' ]]; then
   echo 'TNDS username and/or password not supplied :('
   exit 1
fi

./manage.py import_tnds "$USERNAME" "$PASSWORD"

cd data/variations

for region in F B C M K G D H; do
    old=$(shasum "Bus_Variation_$region.csv")
    wget -qN "https://content.mgmt.dvsacloud.uk/olcs.prod.dvsa.aws/data-gov-uk-export/Bus_Variation_$region.csv"
    new=$(shasum "Bus_Variation_$region.csv")
    if [[ $old != $new ]]; then
        echo $region
        ../../manage.py import_variations < "Bus_Variation_$region.csv"
    fi
done

../../manage.py import_gtfs

finish
