export baseName=tpcq18
export partialPath="umflint/$baseName"
export fullPath="umflint/$baseName/$baseName"

./$baseName.sh
./timing.sh
./runprovenance.sh
./cleanup.sh

unset fullPath
unset partialPath
unset baseName
