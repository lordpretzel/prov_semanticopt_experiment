#python experiments.py -q 10 -r 1 -o -d semanticopt_no_index -R results_n1_no_index
python experiments.py -q 01,02,03,04,05,06,07,08,09,10,11,12,14,17,19,20 -i 100,100,100,100,100,100,5,100,100,100,100,100,100,100,100,100 -o -d semanticopt_no_index -R results_N1_D1GB_Inoindex
# 01,02,03,04,05,06,08,09,10,11,14,17,19,20

#python experiments.py -r 100 -q 14,17,19,20 -o -R results_n1
#python experiments.py -r 100 -q 08,09,10,11,13,14,17,19,20 -m optnoflat -o -R results_n1
#python experiments.py -r 100 -q "14,17,19,20,01" -m optnoflat -o -R results_n1
#python experiments.py -r 5 -q 07 -m optnoflat -o -R results_n1
