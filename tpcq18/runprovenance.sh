if [ ! -d "results" ]; then
  mkdir results
fi

for x in *.sql
do 
  if [[ $x == *"tpc"* ]]; then
    continue
  fi
  v2=${x::-4}
  for x in `seq 1 1`; do \
    psql -h 127.0.0.1 -U postgres -d semanticopt -p 5453 -o /dev/null -c \
    '\timing on' -f $x | grep 'Time:' | awk ' { print $2 }'; \
  done > results/$v2.csv

done
