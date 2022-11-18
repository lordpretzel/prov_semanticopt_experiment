if [ ! -d "results" ]; then
  mkdir results
fi

for sqlfile in *opt.sql
do 
  if [[ ${sqlfile} == *"tpc"* ]]; then
    continue
  fi
  v2=${sqlfile::-4}
  echo "RUN $(pwd)/${sqlfile} SQL FOR TIMING ${v2} STORE IN $(pwd)/results/${v2}.csv"
  for rep in `seq 1 ${repetitions}`; do \
    psql -h 127.0.0.1 -U postgres -d semanticopt -p 5463  -f $(pwd)/${sqlfile} > $(pwd)/results/$v2.txt
  done
    #psql -h 127.0.0.1 -U postgres -d semanticopt -p 5463 -o /dev/null -c \
    #'\timing on' -f $(pwd)/${sqlfile} | grep 'Time:' | awk ' { print $2 }'; \
  #done > $(pwd)/results/$v2.csv

done
