#!/usr/bin/env python3
""" Usage: runner.py <result filename> <path to pypy-c> <revnumber>
"""
from __future__ import division, print_function

import json
import socket
import sys
import os

import benchmarks
from saveresults import save
from unladen_swallow import perf

BENCHMARK_DEFAULT = ['richards', 'spitfire2', 'django',
                     'html5lib', 'ai',
                    ]
if sys.version_info[0] < 3:
    BENCHMARK_DEFAULT += [
                 'spambayes',  # no python3 version
                ]
BENCHMARK_DEFAULT += perf._FindAllBenchmarks(benchmarks.__dict__).keys()
BENCHMARK_FULL = BENCHMARK_DEFAULT + [
                 'pickle', 'unpickle', 'pickle_list', 'unpickle_list',
                 'pickle_dict','call_simple', 'nbody', 'unpack_sequence', 
                 'regex_effbot'
                 ]

CHANGED = 'changed'
BASELINE = 'baseline'


class WrongBenchmark(Exception):
    pass


def run_and_store(benchmark_set, result_filename, changed_path, revision=0,
                  options='', branch='default', args='', upload=False,memory= False,
                  fast=False, baseline_path=sys.executable, full_store=False):
    funcs = perf.BENCH_FUNCS.copy()
    funcs.update(perf._FindAllBenchmarks(benchmarks.__dict__))
    opts = ['-b', ','.join(benchmark_set),
            '--inherit_env=PATH',
            '--no_charts']
    if fast:
        opts += ['--fast']
    if memory:
        opts += ['--track_memory']
    if args:
        opts += ['--args', args]
    if full_store:
        opts += ['--no_statistics']
    opts += [baseline_path, changed_path]
    results = perf.main(opts, funcs)
    f = open(str(result_filename), "w")
    results = [(name, result.__class__.__name__, result.__dict__.get('base_times'))
           for name, result in results]
    opts += ['--track_memory']
    result2 = perf.main(opts, funcs)
    result2 = [(name, result.__dict__.get('max_base'))
           for name, result in result2]
    f.write(json.dumps({
        'revision': revision,
        'results': results,
        'memory' : result2,
        'options': options,
        'branch': branch,
        }, indent=2))
    f.close()
    return results


def get_upload_options(options):
    """
    returns a dict with 2 keys: CHANGED, BASELINE. The values are
    dicts with the keys
    * 'upload' (boolean)
    * 'project' (string)
    * 'executable' (string)
    * 'urls (list of strings).
    * 'branch' (string)
    * 'revision' (string)

    This correspondents to the the --upload* and --upload-baseline*
    options.

    raises: AssertionError if upload is specified, but not the
    corresponding executable or revision.
    """

    if options.upload_baseline_revision is None:
        options.upload_baseline_revision = options.upload_revision

    upload_options = {}

    for run in [CHANGED, BASELINE]:

        def get_upload_option(name):
            attr_name = 'upload'
            if run == BASELINE:
                attr_name = '%s_baseline' % attr_name
            if name:
                attr_name = '%s_%s' % (attr_name, name)
            return getattr(options, attr_name)

        urls = get_upload_option('urls')
        urls = [url.strip() for url in urls.split(',') if url.strip()]
        upload = get_upload_option(None)
        project = get_upload_option('project')
        executable = get_upload_option('executable')
        branch = get_upload_option('branch')
        revision = get_upload_option('revision')
        if upload:
            if executable is None:
                raise AssertionError('If you want to --upload[-baseline] you '
                                     'have to specify the corresponding '
                                     '--upload[-baseline]-executable')
            if revision is None:
                raise AssertionError('If you want to upload the result you '
                                     'have to specify a --revision (or '
                                     '--upload-baseline-revision if you '
                                     'want to upload the baseline result')
            if ((run == BASELINE and 'nullpython.py' in options.baseline) or
                (run == CHANGED and 'nullpython.py' in options.changed)):
                raise AssertionError("Don't upload data from the nullpython "
                                     "dummy interpreter. It won't run any "
                                     "real benchmarks.")

        upload_options[run] = {
            'upload': upload,
            'project': project,
            'executable': executable,
            'urls': urls,
            'branch': branch,
            'revision': revision}
    return upload_options


def main(argv):
    import optparse
    parser = optparse.OptionParser(
        usage="%prog [options]",
        description="Run benchmarks and dump json")

    # benchmark options
    benchmark_group = optparse.OptionGroup(
        parser, 'Benchmark options',
        ('Options affecting the benchmark runs and the resulting output '
         'json file.'))
    benchmark_group.add_option(
        "-b", "--benchmarks", metavar="BM_LIST",
        help=("Comma-separated list of benchmarks to run"
              " Valid benchmarks are: %s"
              ". (default: Run all listed benchmarks)"
              ) % ", ".join(sorted(BENCHMARK_FULL)))
    benchmark_group.add_option(
        "-f", "--benchmarks-file", metavar="BM_FILE",
        help=("Read the list of benchmarks to run from this file (one "
              "benchmark name per line).  Do not specify both this and -b."))
    benchmark_group.add_option(
        '-c', '--changed', default=sys.executable,
        help=('pypy-c or another modified python interpreter to run against. '
              'Also named the "changed" interpreter. (default: the python '
              'used to run this script)'))
    benchmark_group.add_option(
        '--baseline', default=sys.executable, action='store',
        help=('Baseline interpreter. (default: the python used to '
              'run this script)'))
    benchmark_group.add_option(
        '-o', '--output-filename', default="result.json",
        action="store",
        help=('Specify the output filename to store resulting json. '
              '(default: result.json)'))
    benchmark_group.add_option(
        '--options', default='', action='store',
        help='A string describing picked options, no spaces.')
    benchmark_group.add_option(
        '--branch', default='default', action='store',
        dest='upload_branch',
        help=("The branch the 'changed' interpreter was compiled from. This "
              'will be store in the result json and used for the upload. '
              "(default: 'default')"))
    benchmark_group.add_option(
        '-r', '--revision', action="store",
        dest='upload_revision',
        help=("Specify the revision of the 'changed' interpreter. "
              'This will be store in the '
              'result json and used for the upload. (default: None)'))
    benchmark_group.add_option(
        "-a", "--args", default="",
        help=("Pass extra arguments to the python binaries."
              " If there is a comma in this option's value, the"
              " arguments before the comma (interpreted as a"
              " space-separated list) are passed to the baseline"
              " python, and the arguments after are passed to"
              " the changed python. If there's no comma, the"
              " same options are passed to both."))
    benchmark_group.add_option(
        "--fast", default=False, action="store_true",
        help="Run shorter benchmark runs.")
    benchmark_group.add_option("-m", "--track_memory", default=False, action="store_true",
                      help="Track memory usage. This only works on Linux.")
    benchmark_group.add_option(
        "--full-store", default=False, action="store_true",
        help="Run the benchmarks with the --no-statistics flag.")
    parser.add_option_group(benchmark_group)

    # upload changed options
    upload_group = optparse.OptionGroup(
        parser, 'Upload Options',
        ('Options for uploading the result of the "changed" python to '
         'codespeed. The information about revision and branch will '
         'be taken from the options --revision and --branch.'))
    upload_group.add_option(
        "--upload", default=None, action="store_true",
        help=("Upload results to speed.pypy.org (unless "
              "--upload-url is given)."))
    upload_group.add_option(
        "--upload-urls", default="https://speed.pypy.org/",
        help=("Comma seperated urls of the codespeed instances "
              "to upload to. (default: https://speed.pypy.org/)"))
    upload_group.add_option(
        "--upload-project", default="PyPy",
        help="The project name in codespeed. (default: PyPy)")
    upload_group.add_option(
        "--upload-executable", default=None,
        help=("The executable name in codespeed. (required if --upload "
              "is given)"))
    parser.add_option_group(upload_group)
    parser.add_option(
        "--force-host", default=None, action="store",
        help=("Force the hostname. This option will also be used when "
              "uploading the baseline result."))
    parser.add_option("--niceness", default=None, type="int",
                      help="Set absolute niceness for process")

    # upload baseline group
    upload_baseline_group = optparse.OptionGroup(
        parser, 'Upload Baseline Options',
        ('Options for uploading the result of the "baseline" python to '
         'codespeed. The hostname of the --force-host option will be used '
         'in the baseline upload too.'))
    upload_baseline_group.add_option(
        "--upload-baseline", default=None, action="store_true",
        help=("Also upload results or the baseline benchmark "
              "to speed.pypy.org (unless "
              "--upload-baseline-url is given)."))
    upload_baseline_group.add_option(
        "--upload-baseline-urls",
        default="https://speed.pypy.org/",
        help=("Comma seperated urls of the codespeed instances "
              "to upload to. (default: https://speed.pypy.org/)"))
    upload_baseline_group.add_option(
        "--upload-baseline-project", default="PyPy",
        help="The project name in codespeed (default: PyPy).")
    upload_baseline_group.add_option(
        "--upload-baseline-executable", default=None,
        help=("The executable name in codespeed. (required if "
              "--upload-baseline is given)"))
    upload_baseline_group.add_option(
        '--upload-baseline-branch', default='default',
        action='store',
        help=("The name of the branch used for the baseline "
              "run. (default: 'default'"))
    upload_baseline_group.add_option(
        '--upload-baseline-revision', action='store',
        default=None,
        help=("The revision of the baseline. (required if --upload-baseline "
              "is given)"))
    parser.add_option_group(upload_baseline_group)

    # Backward compoatibility options
    deprecated_group = optparse.OptionGroup(
        parser, 'Deprecated Options',
        'Still here for backward compatibility.')
    deprecated_group.add_option(
        '-p', '--pypy-c', default=sys.executable,
        dest='changed', help='Deprecated alias for -c/--changed')
    parser.add_option_group(deprecated_group)

    options, args = parser.parse_args(argv)

    upload_options = get_upload_options(options)
    if options.benchmarks is not None:
        if options.benchmarks_file is not None:
            parser.error(
                '--benchmarks and --benchmarks-file are mutually exclusive')
        else:
            benchmarks = [benchmark.strip()
                          for benchmark in options.benchmarks.split(',')]
    else:
        if options.benchmarks_file is not None:
            benchmarks = []
            try:
                bm_file = open(options.benchmarks_file, 'rt')
            except IOError as e:
                parser.error('error opening benchmarks file: %s' % e)
            with bm_file:
                for line in bm_file:
                    benchmarks.append(line.strip())
        else:
            benchmarks = list(BENCHMARK_DEFAULT)

    for benchmark in benchmarks:
        if benchmark not in BENCHMARK_FULL:
            raise WrongBenchmark(benchmark)

    changed_path = options.changed
    baseline_path = options.baseline
    fast = options.fast
    args = options.args
    full_store = options.full_store
    output_filename = options.output_filename

    branch = options.upload_branch
    revision = options.upload_revision
    force_host = options.force_host
    memory = options.track_memory

    if options.niceness is not None:
        os.nice(options.niceness - os.nice(0))

    results = run_and_store(benchmarks, output_filename, changed_path,
                            revision, args=args, memory= memory, fast=fast,
                            baseline_path=baseline_path,
                            full_store=full_store, branch=branch)

    errors = []
    for run in [CHANGED, BASELINE]:
        upload = upload_options[run]['upload']
        urls = upload_options[run]['urls']
        project = upload_options[run]['project']
        executable = upload_options[run]['executable']
        branch = upload_options[run]['branch'] or 'default'
        revision = upload_options[run]['revision']

        if upload:
            # prevent to upload results from the nullpython dummy
            host = force_host if force_host else socket.gethostname()
            for url in urls:
                try:
                    print(save(project, revision, results, executable, host, url,
                           changed=(run == CHANGED), branch=branch))
                except IOError as e:
                    errors.append(e)
    if len(errors) > 0:
        raise errors[0]


if __name__ == '__main__':
    main(sys.argv[1:])
