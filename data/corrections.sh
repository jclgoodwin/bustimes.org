#!/bin/bash


# Reading Friar Street Stop FH -> FC

sed -i '' 's/>039026100002</>039028170001</' \
    SE/set_4-127-_-y08-1.xml SE/set_4-128-_-y08-1.xml SE/set_4-129-_-y08-1.xml
sed -i '' 's/>stop FH</>stop FC</' SE/set_4-128-_-y08-1.xml \
    SE/set_4-127-_-y08-1.xml SE/set_4-128-_-y08-1.xml SE/set_4-129-_-y08-1.xml


# Reepham opp -> adj Market Place

sed -i '' 's/>2900R0513</>2900R053</' \
    EA/ea_21-45A-_-y08-1.xml
