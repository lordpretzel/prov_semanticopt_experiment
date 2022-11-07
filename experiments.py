import os
import argparse
import re
#import sys
import subprocess
from dataclasses import dataclass
from typing import List

# Queries and the provenance tables we want to use
queries = {
    "01": ["lineitem"],
    "02": ["nation", "part", "partsupp", "region"],
    "03": ["customer", "lineitem", "orders"],
    "04": ["lineitem", "orders"],
    "05": ["customer", "lineitem", "nation", "orders", "region"],
    "06": ["lineitem"],
    "07": ["customer", "lineitem", "nation", "orders", "supplier"],
    "08": ["customer", "nation", "part", "supplier"],
    "09": ["lineitem", "nation", "orders", "part", "partsupp", "supplier"],
    "10": ["customer", "lineitem", "nation", "orders"],
    "11": ["nation", "partsupp", "supplier"],
    "12": ["lineitem", "orders"],
    "13": ["customer", "orders"],
    "14": ["lineitem", "part"],
    "15": ["lineitem", "supplier"],
    "16": ["part", "partsupp", "supplier"],
    "17": ["lineitem", "part"],
    "18": ["customer", "lineitem", "orders"],
    "19": ["lineitem", "part"],
    "20": ["part"],
    }

@dataclass
class GpromSetting:
    name: str
    args: List


gprom_settings = [
    GpromSetting("flatten", ["-Osemantic_opt","FALSE", "-Oflatten_dl", "TRUE" ]),
    GpromSetting("opt", ["-Osemantic_opt","TRUE", "-Oflatten_dl", "TRUE" ]),
]

GPROM_BIN = "/home/perm/semantic_opt_gprom/src/command_line/gprom"
DEBUG_ARGS = [ "-loglevel" ]
options = None

def get_debug_args():
    return DEBUG_ARGS + [ str(options.loglevel) ]

def log(m):
    print(m)

def logfat(m, other=""):
    log(80 * "=" + "\n" + m + "\n" + 80 * "=" + "\n" + other)
    
def qdir(q):
    return f"{os.getcwd()}/tpcq{q}/"

def get_shell_command_results(cmd):
    process = subprocess.run(cmd,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             universal_newlines=True)
    return (process.returncode, process.stdout.strip(), process.stderr.strip())

def psql_cmd(cmd: str) -> int:
    return get_shell_command_results(f'psql -h {options.host} -U {options.user} -d {options.db} -p {str(options.port)} -c'.split(" ") + [f'{cmd}'])

def psql_connection_args():
    return [ '-h', options.host, '-U', options.user, '-d', options.db, '-p', str(options.port) ]

def psql_read_file_as_list(cmd):
    return ['psql'] + psql_connection_args() + [ "-c", "\\timing on" ] + [ '-f', cmd ]


def psql_file_to_string(f):
    cmd = psql_read_file_as_list(f)
    log(f'run PSQL:\n {" ".join(cmd)}')
    return get_shell_command_results(cmd)

def psql_time(infile, outfile, repetitions):
    with open(outfile, "w") as f:
        for i in range(repetitions):
            log(f"ITERATION: {i+1} of {repetitions}")
            (rt,out,err) = psql_file_to_string(infile)
            if rt:
                log(f"error timing command with psql [{rt}]:\n{err}\n{out}")
                exit(rt)
            log(out[0:min(len(out), 1000)])
            t = re.search("Time: ([0-9.]+)", out).group(1)
            log(f"took {t} ms") 
            f.write(t + "\n")

def gprom_connection_options():
    return f'-backend postgres -host {options.host} -user {options.user} -passwd {options.password} -port {str(options.port)} -db {options.db} -frontend dl'

def gprom_command(gprom_opts, f=None):
    fstr = f'-queryFile "{f}"' if f else ""
    cmd = f'{options.gprom} {gprom_connection_options()} {" ".join(gprom_opts)} {fstr}'
    return cmd

def gprom_connection_options_as_list():
    return ['-backend', 'postgres', '-host' , options.host,  '-user', options.user, '-passwd', options.password, '-port', str(options.port), '-db', options.db, '-frontend', 'dl', '-Loperator_verbose', 'TRUE']

def gprom_command_as_list(gprom_opts, f=None):
    fopts = ["-queryFile", f"{f}"] if f else []
    cmd = [ options.gprom ] + gprom_connection_options_as_list() + gprom_opts + fopts
    return cmd

def run_gprom(gprom_opts, f=None):
    cmd = gprom_command_as_list(gprom_opts, f)
    return get_shell_command_results(cmd)

def run_gprom_store_output(gprom_opts, inf, outf):
    cmd = gprom_command_as_list(gprom_opts, inf)
    log(f'run {" ".join(cmd)}\n to execute {inf} and store output in {outf}')
    with open(outf, 'w') as f:
        process = subprocess.run(cmd,
                                 stdout=f,
                                 stderr=subprocess.PIPE,
                                 universal_newlines=True)
        rt = process.returncode
        if rt:
            log(f'error running commands from {inf} and storing result in {outf} using command line:\n{cmd}')

        return (rt, process.stderr)

def materialize_result_subset(q):
    logfat(f"create table for {q}") 
    dlfile = qdir(q) + "tpcq" + q + ".dl"
    sqlfile = qdir(q) + "tpcq" + q + ".sql"
    if options.debug:
        (rt,sql,err) = run_gprom(["-Pexecutor", "sql"] + get_debug_args(), dlfile)
        log(f"EXECUTION [{rt}]:\n\n{sql}\n\n{err}")
    
    (rt,sql,err) = run_gprom(["-Pexecutor", "sql","-loglevel","0"], dlfile)
    if rt:
        log(f"error running gprom {dlfile} [ERR:{rt}]:\n{err}\n{sql}")
        exit(rt)
    if not options.overwrite and os.path.exists(sqlfile):
        log(f"do not overwrite file {sqlfile}")
    else:
        with open(sqlfile, "w") as f:
            f.write(sql)
    #TODO check that table has the number of rows we need
    create_table = f"CREATE TABLE IF NOT EXISTS {get_result_table(q)} AS ({sql}"[0:-1] + " LIMIT 1);"
    log(f"created table:\n{create_table}")
    (rt,out,err) = psql_cmd(create_table)
    if rt:
        log(f"error creating table for {q} [exit code: {rt}]:\n{out}\n{err}")
        exit(rt)

def generate_rewritten_sql(q):
    d = qdir(q)
    common_opts = ['-loglevel', '0', '-Pexecutor', 'sql']
    for pt in queries[q]:
        infile = d + f"{pt}.dl"
        for s in gprom_settings:
            outfile = d + f"p_{pt}_{s.name}.sql"
            logfat(f"generate sql for {s.name} for {q}")
            if options.debug:
                (rt, out, err) = run_gprom(common_opts + s.args + get_debug_args(), infile)
                log(out)
            if os.path.exists(outfile) and not options.overwrite:
                log("do not overwrite file {outfile}")
            else:
                (rt, err) = run_gprom_store_output(common_opts + s.args, infile, outfile)
                if rt:
                    log(f"error generating rewritting SQL for {s.name} for {q} [{rt}]:\n{err}")
                
def get_result_table(query):
    return f"rtpcq{query}"

def cleanup_result_table(q):    
    logfat(f"dropped result table {get_result_table(q)}")
    psql_cmd(f"DROP TABLE {get_result_table(q)};")

def time_provenance_capture(q):
    d = qdir(q)
    for pt in queries[q]:
        for s in gprom_settings:
            logfat(f"time runtime {s.name} for {q} with {str(options.repetitions)} repetitions")
            infile = d + f"p_{pt}_{s.name}.dl"
            outfile = options.resultdir + "/" + f"runtime_{q}_{pt}_{s.name}.csv"
            if os.path.exists(outfile) and not options.overwrite:
                log(f"do not overwrite file {outfile}")
            else:
                psql_time(infile, outfile, options.repetitions)

def process_one_query(q):
    d = qdir(q)
    if not os.path.exists(d):
        log(f"missing directory {d}")
        exit(1)

    if not options.only or options.only == 'table':
        materialize_result_subset(q)
    if not options.only or options.only == 'gensql':
        generate_rewritten_sql(q)
    if not options.only or options.only == 'time':
        time_provenance_capture(q)
    if (options.cleanup and options.only is None) or options.only == 'cleanup':
        cleanup_result_table(q)
    
def main(args):
    global options
    options = args
    if not os.path.exists(options.resultdir):
        os.mkdir(options.resultdir)
    if args.queries:
        for q in args.queries.strip().split(","):
            logfat(f"process query q{q}")
            process_one_query(q)
    else:
        for q in queries:
            logfat(f"process query q{q}")
            process_one_query(q)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Running semantic optimization experiment')
    ap.add_argument('-r', '--repetitions', type=int, default=1,
                    help="number of repetitions for each experiment")
    ap.add_argument('-q', '--queries', type=str, default=None,
                    help="run only this query (default is to run all)")
    ap.add_argument('--gprom', type=str, default=GPROM_BIN,
                    help="use this gprom binary")
    ap.add_argument('-o', '--overwrite', action='store_true',
                    help="overwrite existing files")
    ap.add_argument('-c', '--cleanup', action='store_true',
                    help="cleanup by dropping table with result row")
    ap.add_argument('-n', '--num-result-rows', type=int, default=1,
                    help="compute provenance for this many result row")
    ap.add_argument("-R", "--resultdir", type=str, default="results",
                    help="store results in this folder")

    ap.add_argument("-D", "--debug", action='store_true',
                    help="debug the process by logging more information.")
    ap.add_argument("-l", "--loglevel", type=int, default=3,
                    help="log level to use when debugging.")
    
    ap.add_argument("-H", "--host", type=str, default="127.0.0.1",
                    help="database host")
    ap.add_argument("-u", "--user", type=str, default="postgres",
                    help="database user")
    ap.add_argument("-p", "--port", type=int, default=5463,
                    help="database port")
    ap.add_argument("-d", "--db", type=str, default="semanticopt",
                    help="database name")
    ap.add_argument("-P", "--password", type=str, default="test",
                    help="database password")

    ap.add_argument("--only", type=str, default=None,
                    help="only execute one step (table, gensql, time, clean)")
    
    args = ap.parse_args()
    
    main(args)

        
