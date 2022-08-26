baseName="tpcq16"
fullPath="umflint/$baseName"

for x in *.dl
do 
  if [[ $x == *"tpc"* ]]; then
    continue
  fi
  v2=${x::-3}
  cd ../..
  ./src/command_line/gprom -backend postgres -host 127.0.0.1 -user postgres -db>
    semanticopt -port 5463 -passwd test -frontend dl -Osemantic_opt TRUE \
    -Oflatten_dl TRUE -loglevel 0 -Pexecutor sql -queryFile \
    $fullPath/$v2.dl > $fullPath/"p_"${v2}"_opt.sql"

  ./src/command_line/gprom -backend postgres -host 127.0.0.1 -user postgres -db>
     semanticopt -port 5463 -passwd test -frontend dl -Osemantic_opt FALSE \
     -Oflatten_dl TRUE -loglevel 0 -Pexecutor sql -queryFile \
     $fullPath/$v2.dl > $fullPath/"p_"${v2}"_unopt.sql"
