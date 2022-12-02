export baseName=tpcq16
export partialPath="umflint/$baseName"
export fullPath="umflint/$baseName/$baseName"
export repetitions=1

echo "================================================================================
RUN: $baseName.sh"
./$baseName.sh
echo "================================================================================
RUN: timing.sh"
./timing.sh
echo "================================================================================
RUN: ./runprovenance.sh"
#./runprovenance.sh
echo "================================================================================
RUN: ./cleanup.sh"
#./cleanup.sh

unset fullPath
unset partialPath
unset baseName
