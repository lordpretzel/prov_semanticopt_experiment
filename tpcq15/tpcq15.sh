#!/bin/bash

echo CREATE TABLE r$baseName AS > $baseName.sql
cd ../..
./run_gprom.sh -Pexecutor sql -queryFile $fullPath.dl -loglevel 0 >> $fullPath.>

sed -i 's/;/ LIMIT 1;/g' $fullPath.sql

psql -h 127.0.0.1 -U postgres -d semanticopt -p 5463 -f $fullPath.sql

