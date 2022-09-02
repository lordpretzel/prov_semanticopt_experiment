echo "RUN TIMING WITH: partialPath=$partialPath"

for x in *.dl
do
  if [[ $x == *"tpc"* ]]; then
    continue
  fi
  v2=${x::-3}
  echo "TIME FILE: ${v2}"  
  pushd ../..
  echo "WORKING FROM: $(pwd)"
    echo "From $(pwd)/${partialPath}/${v2}.dl GENERATE $(pwd)/${partialPath}/p_${v2}_opt.sql"
  ./src/command_line/gprom -backend postgres -host 127.0.0.1 -user postgres -db \
    semanticopt -port 5463 -passwd test -frontend dl -Osemantic_opt TRUE \
    -Oflatten_dl TRUE -loglevel 0 -Pexecutor sql -queryFile \
    "$(pwd)/${partialPath}/${v2}.dl" > "$(pwd)/${partialPath}/p_${v2}_opt.sql"
  
    echo "From $(pwd)/${partialPath}/${v2}.dl GENERATE $(pwd)/${partialPath}/p_${v2}_unopt.sql"
  ./src/command_line/gprom -backend postgres -host 127.0.0.1 -user postgres -db \
     semanticopt -port 5463 -passwd test -frontend dl -Osemantic_opt FALSE \
     -Oflatten_dl TRUE -loglevel 0 -Pexecutor sql -queryFile \
     "$(pwd)/${partialPath}/${v2}.dl" > "$(pwd)/${partialPath}/p_${v2}_unopt.sql"
  
  popd
done
