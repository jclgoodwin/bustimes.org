#!/bin/bash


# Reading Friar Street Stop FH -> FC

sed -i'.bak' 's/>039026100002</>039028170001</' \
    SE/set_4-127-_-y08-1.xml SE/set_4-128-_-y08-1.xml SE/set_4-129-_-y08-1.xml
sed -i'.bak' 's/>stop FH</>stop FC</' SE/set_4-128-_-y08-1.xml \
    SE/set_4-127-_-y08-1.xml SE/set_4-128-_-y08-1.xml SE/set_4-129-_-y08-1.xml


# Reepham opp -> adj Market Place

sed -i'.bak' 's/>2900R0513</>2900R053</' \
    EA/ea_21-45A-_-y08-1.xml


sed -i'.bak' 's/<Monday \/>//'      S/SVRHIAO89*.xml
sed -i'.bak' 's/<Tuesday \/>//'     S/SVRHIAO89*.xml
sed -i'.bak' 's/<Tuesday \/>//'     S/SVRHIAO89*.xml
sed -i'.bak' 's/<Wednesday \/>//'   S/SVRHIAO89*.xml

sed -i'.bak' 's/<Friday \/>//'      S/SVRHIAO89*.xml
sed -i'.bak' 's/<Saturday \/>//'    S/SVRHIAO89*.xml
sed -i'.bak' 's/<Sunday \/>//'      S/SVRHIAO89*.xml
sed -i'.bak' 's/<ServicedOrganisationDayType>//'    S/SVRHIAO89*.xml
sed -i'.bak' 's/ <DaysOfNonOperation>//'            S/SVRHIAO89*.xml
sed -i'.bak' 's/  <WorkingDays>//'                  S/SVRHIAO89*.xml
sed -i'.bak' 's/   <ServicedOrganisationRef>285<\/ServicedOrganisationRef>//' S/SVRHIAO89*.xml
sed -i'.bak' 's/  <\/WorkingDays>//'                S/SVRHIAO89*.xml
sed -i'.bak' 's/ <\/DaysOfNonOperation>//'          S/SVRHIAO89*.xml
sed -i'.bak' 's/<\/ServicedOrganisationDayType>//'  S/SVRHIAO89*.xml

sed -i'.bak' 's/<VehicleJourney>/<VehicleJourney><Note><NoteText>1st and 3rd Thursday of each month only<\/NoteText><\/Note>/' S/SVRHIAO890.xml
sed -i'.bak' 's/<VehicleJourney>/<VehicleJourney><Note><NoteText>4th Thursday of each month only<\/NoteText><\/Note>/' S/SVRHIAO891.xml

rm ./*/*.bak
