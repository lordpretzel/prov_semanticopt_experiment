import os
import argparse
import re
#import sys
import subprocess
from dataclasses import dataclass
from typing import List
from math import ceil
import rich

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
    GpromSetting("unopt", ["-Osemantic_opt","FALSE", "-Oflatten_dl", "FALSE" ]),
    GpromSetting("flatten", ["-Osemantic_opt","FALSE", "-Oflatten_dl", "TRUE" ]),
    GpromSetting("opt", ["-Osemantic_opt","TRUE", "-Oflatten_dl", "TRUE" ]),
    GpromSetting("optnoflat", ["-Osemantic_opt", "TRUE", "-Oflatten_dl", "FALSE"]),
    GpromSetting("optheu", ["-Osemantic_opt","TRUE", "-Oflatten_dl", "TRUE", "-heuristic_opt", "TRUE" ]),
    GpromSetting("unoptheu", ["-Osemantic_opt","FALSE", "-Oflatten_dl", "FALSE", "-heuristic_opt", "TRUE" ]),
    GpromSetting("optcbo", ["-Osemantic_opt","TRUE", "-Oflatten_dl", "TRUE", "-heuristic_opt", "TRUE",  "-cbo", "TRUE"]),
]

GPROM_BIN = "/home/perm/semantic_opt_gprom/src/command_line/gprom"
DEBUG_ARGS = [ "-loglevel" ]
options = None

def get_debug_args():
    return DEBUG_ARGS + [ str(options.loglevel) ]

def log(m):
    print(m)

def logfat(m, other=""):
    rich.print("\n[b black on white]" + 80 * " " + "\n" + m + "\n" + 80 * " " + "\n" + other + "[/]")

def qdir(q):
    return f"{os.getcwd()}/tpcq{q}/"

def ensure_file_exists(f):
    if not os.path.exists(f):
        log(f"sql file <{f}> does not exist")
        exit(1)

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
            match = re.search("Time: ([0-9.]+)", out)
            if match:
                t = match.group(1)
                log(f"took {t} ms")
                f.write(t + "\n")
            else:
                f.write("NaN\n")

def psql_explain(infile, outfile):
    with open(outfile, "w") as f:
        (rt,out,err) = psql_file_to_string(infile)
        if options.debug:
            log(out)
        f.write(out)
        if rt:
            log(f"error explaining SQL with psql [{rt}]:\n{err}\n{out}")
            exit(rt)
            log(out[0:min(len(out), 1000)])

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
    try:
        with open(outf, 'w') as f:
            process = subprocess.run(cmd,
                                     stdout=f,
                                     stderr=subprocess.PIPE,
                                     universal_newlines=True)
            rt = process.returncode
            if rt:
                log(f'error running commands from {inf} and storing result in {outf} using command line:\n{cmd}')

            return (rt, process.stderr)
    except Exception as e:
        return (-1, f"error writing GProM results to file:\n{e}")


def get_num_result_rows(q):
    count_results = f"SELECT count(*) FROM ({q[0:-1]}) sub;"
    (rt,out,err) = psql_cmd(count_results)
    if rt:
        log(f"error running gprom to count results [ERR:{rt}]:\n{err}\n{q}")
        exit(rt)
    else:
        snd = out.split("\n")[2]
        return int(snd.strip())
        
def materialize_result_subset(q):
    logfat(f"create table for {q}")
    dlfile = qdir(q) + "tpcq" + q + ".dl"
    ensure_file_exists(dlfile)
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
    ensure_file_exists(sqlfile)
    if options.overwrite:
        cleanup_result_table(q)
    #TODO check that table has the number of rows we need
    prov_num_results = options.num_result_rows
    prov_absolute_results = options.num_result_rows_absolute
    # get actual number of result rows to determine percentage and skip if there are not enough
    if not prov_absolute_results:
        actual_num_results = get_num_result_rows(sql)
        prov_num_results = ceil((0.01 * prov_num_results) * actual_num_results)

    create_table = f"CREATE TABLE IF NOT EXISTS {get_result_table(q)} AS ({sql}"[0:-1] + f" LIMIT {prov_num_results});"
    log(f"created table:\n{create_table}")
    (rt,out,err) = psql_cmd(create_table)
    if rt:
        log(f"error creating table for {q} [exit code: {rt}]:\n{out}\n{err}")
        exit(rt)
    analyze = f"ANALYZE {get_result_table(q)};"
    (rt,out,err) = psql_cmd(analyze)
    if rt:
        log(f"error analzying table for {q} [exit code: {rt}]:\n{out}\n{err}")
        exit(rt)


def generate_rewritten_sql(q):
    d = qdir(q)
    common_opts = ['-loglevel', '0', '-Pexecutor', 'sql']
    tables = options.tables.split(',') if options.tables else queries[q]
    for pt in tables:
        infile = d + f"{pt}.dl"
        ensure_file_exists(infile)
        for s in options.methods:
            outfile = d + f"p_{pt}_{s.name}.sql"
            logfat(f"generate sql for {s.name} for {q} for provenance of {pt}")
            log(f"sql file: {outfile} from dl file {infile}")
            if options.debug:
                (rt, out, err) = run_gprom(common_opts + s.args + get_debug_args(), infile)
                log(out)
            if os.path.exists(outfile) and not options.overwrite:
                log(f"do not overwrite file {outfile}")
            else:
                (rt, err) = run_gprom_store_output(common_opts + s.args, infile, outfile)
                if rt:
                    log(f"error generating rewritting SQL for {s.name} for {q} [{rt}]:\n{err}")

def generate_rewritten_datalog(q):
    d = qdir(q)
    common_opts = ['-loglevel', '0', '-Ptranslator', 'dl-to-dl', '-Psqlserializer', 'dl', '-Pexecutor', 'dl'] # '-loglevel', '5']
    tables = options.tables.split(',') if options.tables else queries[q]
    for pt in tables:
        infile = d + f"{pt}.dl"
        ensure_file_exists(infile)
        for s in options.methods:
            outfile = d + f"p_{pt}_{s.name}.dl"
            logfat(f"generate rewritten datalog for {s.name} for {q} for provenance of {pt}")
            log(f"rewritten dl file: {outfile} from dl file {infile}")
            if options.debug:
                (rt, out, err) = run_gprom(common_opts + s.args + get_debug_args(), infile)
                log(out)
            if os.path.exists(outfile) and not options.overwrite:
                log(f"do not overwrite file {outfile}")
            else:
                (rt, err) = run_gprom_store_output(common_opts + s.args, infile, outfile)
                if rt:
                    log(f"error generating rewritting datalog for {s.name} for {q} [{rt}]:\n{err}")

def get_result_table(query):
    return f"rtpcq{query}"

def get_all_result_table(query):
    return f"rtpcq_all_{query}"

def cleanup_result_table(q):
    logfat(f"dropped result table {get_result_table(q)}")
    psql_cmd(f"DROP TABLE IF EXISTS {get_result_table(q)};")

def time_provenance_capture(q):
    d = qdir(q)
    reps = options.individual_repetitions[q] if options.individual_repetitions else options.repetitions
    tables = options.tables.split(',') if options.tables else queries[q]
    for pt in tables:
        for s in options.methods:
            logfat(f"time runtime {s.name} for {q} for provenance of {pt} with {str(options.repetitions)} repetitions")
            infile = d + f"p_{pt}_{s.name}.sql"
            ensure_file_exists(infile)
            outfile = options.resultdir + "/" + f"runtime_{q}_{pt}_{s.name}.csv"
            if os.path.exists(outfile) and not options.overwrite:
                log(f"do not overwrite file {outfile}")
            else:
                psql_time(infile, outfile, reps)

def explain_sql_query(q):
    d = qdir(q)
    tables = options.tables.split(',') if options.tables else queries[q]
    for pt in tables:
        for s in options.methods:
            logfat(f"generate explanation {s.name} for {q} for provenance of {pt}")
            infile = d + f"p_{pt}_{s.name}.sql"
            explainfile = d + f"explain_p_{pt}_{s.name}.sql"
            ensure_file_exists(infile)
            outfile = d  + f"plan_{q}_{pt}_{s.name}.txt"
            if os.path.exists(outfile) and not options.overwrite:
                log(f"do not overwrite file {outfile}")
            else:
                with open(explainfile, 'w') as efile:
                    with open(infile, 'r') as sqlfile:
                        code = sqlfile.readlines()
                    efile.write('EXPLAIN\n')
                    efile.write('\n'.join(code))
                psql_explain(explainfile, outfile)

def process_one_query(q):
    d = qdir(q)
    if not os.path.exists(d):
        log(f"missing directory {d}")
        exit(1)

    if not options.only or 'table' in options.only:
        materialize_result_subset(q)
    if not options.only or 'gensql' in options.only:
        generate_rewritten_sql(q)
    if not options.only or 'gendl' in options.only:
        generate_rewritten_datalog(q)
    if not options.only or 'time' in options.only:
        time_provenance_capture(q)
    if options.only and 'explain' in options.only:
        explain_sql_query(q)
    if (options.cleanup and not options.only) or (options.only and 'cleanup' in options.only):
        cleanup_result_table(q)

def main(args):
    global options
    options = args

    # process options with list arguments
    options.only = options.only.strip().split(",") if options.only else None
    options.queries = options.queries.strip().split(",") if options.queries else queries
    options.methods = [ g for g in gprom_settings if g.name in options.methods.strip().split(",") ] if options.methods else gprom_settings
    if options.individual_repetitions:
        options.individual_repetitions = [ int(x) for x in options.individual_repetitions.strip().split(",") ]
        if len(options.individual_repetitions) != len(options.queries):
            print(f"if individual number of repetitions for queries are given then the number of entries has to match the number of queries, but {len(options.individual_repetitions)} != {len(options.queries)}")
            exit(1)
        options.individual_repetitions = { options.queries[i]: options.individual_repetitions[i] for i in range(len(options.individual_repetitions)) }

    if not os.path.exists(options.resultdir):
        os.mkdir(options.resultdir)
    for q in options.queries:
        logfat(f"process query q{q}")
        process_one_query(q)

def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Running semantic optimization experiment')
    ap.add_argument('-r', '--repetitions', type=int, default=1,
                    help="number of repetitions for each experiment")
    ap.add_argument('-i', '--individual-repetitions', type=str, default=None,
                    help="number of repetitions for each experiment (specified for individual queries)")
    ap.add_argument('-q', '--queries', type=str, default=None,
                    help=f"run only this query (default is to run all: {queries.keys()})")
    ap.add_argument('-m', '--methods', type=str, default=None,
                    help=f"run only these methods (default is to run all: {[ m.name for m in gprom_settings ]}")
    ap.add_argument('--gprom', type=str, default=GPROM_BIN,
                    help="use this gprom binary")
    ap.add_argument('-o', '--overwrite', action='store_true',
                    help="overwrite existing files")
    ap.add_argument('-c', '--cleanup', action='store_true',
                    help="cleanup by dropping table with result row")
    ap.add_argument('-A', '--num_result_rows_absolute', type=str2bool, nargs='?', const=True, default=True,
                    help="If true then the number of result rows are specified as an absolute number, otherwise as a percentage of the total result rows for a query")
    ap.add_argument('-n', '--num_result_rows', type=int, default=1,
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

    ap.add_argument('-O', "--only", type=str, default=None,
                    help="only execute only listed steps (table, gensql, gendl, explain, time, clean) separated by comma")

    ap.add_argument('-T', "--tables", type=str, default=None,
                    help="only capture provenance (or apply other steps) for these tables")

    args = ap.parse_args()

    rich.print("[b black on white]Configuration" + (70 * " ") + "[/]\n", args, "\n[b black on white]" + (80 * " ") + "[\]")

    main(args)
