import os
import re
import time
import warnings
import tempfile

import pkg_resources
import pytest
from _pytest.runner import runtestprotocol
from sqlitedict import SqliteDict
from functools import lru_cache
from contextlib import contextmanager

HAS_RESULTLOG = False

try:
    from _pytest.resultlog import ResultLog

    HAS_RESULTLOG = True
except ImportError:
    # We have a pytest >= 6.1
    pass


PYTEST_GTE_54 = pkg_resources.parse_version(
    pytest.__version__
) >= pkg_resources.parse_version("5.4")

PYTEST_GTE_63 = pkg_resources.parse_version(
    pytest.__version__
) >= pkg_resources.parse_version("6.3.0.dev")


def works_with_current_xdist():
    """Returns compatibility with installed pytest-xdist version.

    When running tests in parallel using pytest-xdist < 1.20.0, the first
    report that is logged will finish and terminate the current node rather
    rerunning the test. Thus we must skip logging of intermediate results under
    these circumstances, otherwise no test is rerun.

    """
    try:
        d = pkg_resources.get_distribution("pytest-xdist")
        return d.parsed_version >= pkg_resources.parse_version("1.20")
    except pkg_resources.DistributionNotFound:
        return None


# command line options
def pytest_addoption(parser):
    group = parser.getgroup(
        "rerunfailures", "re-run failing tests to eliminate flaky failures"
    )
    group._addoption(
        "--only-rerun",
        action="append",
        dest="only_rerun",
        type=str,
        default=None,
        help="If passed, only rerun errors matching the regex provided. "
        "Pass this flag multiple times to accumulate a list of regexes "
        "to match",
    )
    group._addoption(
        "--reruns",
        action="store",
        dest="reruns",
        type=int,
        default=0,
        help="number of times to re-run failed tests. defaults to 0.",
    )
    group._addoption(
        "--reruns-delay",
        action="store",
        dest="reruns_delay",
        type=float,
        default=0,
        help="add time (seconds) delay between reruns.",
    )


def pytest_configure(config):
    # add flaky marker
    config.addinivalue_line(
        "markers",
        "flaky(reruns=1, reruns_delay=0): mark test to re-run up "
        "to 'reruns' times. Add a delay of 'reruns_delay' seconds "
        "between re-runs.",
    )


def _get_resultlog(config):
    if not HAS_RESULTLOG:
        return None
    elif PYTEST_GTE_54:
        # hack
        from _pytest.resultlog import resultlog_key

        return config._store.get(resultlog_key, default=None)
    else:
        return getattr(config, "_resultlog", None)


def _set_resultlog(config, resultlog):
    if not HAS_RESULTLOG:
        pass
    elif PYTEST_GTE_54:
        # hack
        from _pytest.resultlog import resultlog_key

        config._store[resultlog_key] = resultlog
    else:
        config._resultlog = resultlog


# making sure the options make sense
# should run before / at the beginning of pytest_cmdline_main
def check_options(config):
    val = config.getvalue
    if not val("collectonly"):
        if config.option.reruns != 0:
            if config.option.usepdb:  # a core option
                raise pytest.UsageError("--reruns incompatible with --pdb")

    resultlog = _get_resultlog(config)
    if resultlog:
        logfile = resultlog.logfile
        config.pluginmanager.unregister(resultlog)
        new_resultlog = RerunResultLog(config, logfile)
        _set_resultlog(config, new_resultlog)
        config.pluginmanager.register(new_resultlog)


def _get_marker(item):
    try:
        return item.get_closest_marker("flaky")
    except AttributeError:
        # pytest < 3.6
        return item.get_marker("flaky")


def get_reruns_count(item):
    rerun_marker = _get_marker(item)
    reruns = None

    # use the marker as a priority over the global setting.
    if rerun_marker is not None:
        if "reruns" in rerun_marker.kwargs:
            # check for keyword arguments
            reruns = rerun_marker.kwargs["reruns"]
        elif len(rerun_marker.args) > 0:
            # check for arguments
            reruns = rerun_marker.args[0]
        else:
            reruns = 1
    elif item.session.config.option.reruns:
        # default to the global setting
        reruns = item.session.config.option.reruns

    return reruns


def get_reruns_delay(item):
    rerun_marker = _get_marker(item)

    if rerun_marker is not None:
        if "reruns_delay" in rerun_marker.kwargs:
            delay = rerun_marker.kwargs["reruns_delay"]
        elif len(rerun_marker.args) > 1:
            # check for arguments
            delay = rerun_marker.args[1]
        else:
            delay = 0
    else:
        delay = item.session.config.option.reruns_delay

    if delay < 0:
        delay = 0
        warnings.warn(
            "Delay time between re-runs cannot be < 0. Using default value: 0"
        )

    return delay


def get_reruns_condition(item):
    rerun_marker = _get_marker(item)

    condition = True
    if rerun_marker is not None and "condition" in rerun_marker.kwargs:
        condition = rerun_marker.kwargs["condition"]

    return condition


def _remove_cached_results_from_failed_fixtures(item):
    """
    Note: remove all cached_result attribute from every fixture
    """
    cached_result = "cached_result"
    fixture_info = getattr(item, "_fixtureinfo", None)
    for fixture_def_str in getattr(fixture_info, "name2fixturedefs", ()):
        fixture_defs = fixture_info.name2fixturedefs[fixture_def_str]
        for fixture_def in fixture_defs:
            if getattr(fixture_def, cached_result, None) is not None:
                result, cache_key, err = getattr(fixture_def, cached_result)
                if err:  # Deleting cached results for only failed fixtures
                    if PYTEST_GTE_54:
                        setattr(fixture_def, cached_result, None)
                    else:
                        delattr(fixture_def, cached_result)


def _remove_failed_setup_state_from_session(item):
    """
    Note: remove all failures from every node in _setupstate stack
          and clean the stack itself
    """
    setup_state = item.session._setupstate
    if PYTEST_GTE_63:
        setup_state.stack = {}
    else:
        for node in setup_state.stack:
            if hasattr(node, "_prepare_exc"):
                del node._prepare_exc
        setup_state.stack = []


def _should_hard_fail_on_error(session_config, report):
    if report.outcome != "failed":
        return False

    rerun_errors = session_config.option.only_rerun
    if not rerun_errors:
        return False

    for rerun_regex in rerun_errors:
        if re.search(rerun_regex, report.longrepr.reprcrash.message):
            return False

    return True


def _should_not_rerun(item, report, reruns):
    xfail = hasattr(report, "wasxfail")
    is_terminal_error = _should_hard_fail_on_error(item.session.config, report)
    condition = get_reruns_condition(item)
    return (
        item.execution_count > reruns
        or not report.failed
        or xfail
        or is_terminal_error
        or not condition
    )


def is_master(config):
    return not (hasattr(config, "workerinput") or hasattr(config, "slaveinput"))


def pytest_configure(config):
    if is_master(config):
        fp = tempfile.NamedTemporaryFile()
        fp.close()
        with open(fp.name, 'w+') as _:
            pass

        config.failures_log = fp.name


def pytest_unconfigure(config):
    if is_master(config):
        os.remove(config.failures_log)


def pytest_configure_node(node):
    """xdist hook"""
    node.workerinput['failures_log'] = node.config.failures_log


def failures_log(config):
    if is_master(config):
        return config.failures_log
    else:
        return config.workerinput['failures_log']


@lru_cache(maxsize=5)
def failures_db(path):
    return StatusDB(path)


def log_db(config):
    return failures_db(failures_log(config))


class StatusDB(object):
    def __init__(self, path):
        self.db = SqliteDict(path)

    @contextmanager
    def _record(self, item):
        with self.db as db:
            if item in db:
                record = db[item]
            else:
                record = {'failures': 0, 'reruns': 0}

        failures, reruns = record['failures'], record['reruns']
        yield record
        if record['failures'] == failures and record['reruns'] == reruns:
            return

        with self.db as db:
            db[item] = record
            db.commit()

    def add_test_failure(self, crashitem):
        with self._record(crashitem) as record:
            record['failures'] += 1

    def get_test_failures(self, crashitem):
        with self._record(crashitem) as record:
            return record['failures']

    def set_test_reruns(self, crashitem, reruns):
        with self._record(crashitem) as record:
            record['reruns'] = reruns

    def get_test_reruns(self, crashitem):
        with self._record(crashitem) as record:
            return record['reruns']


def pytest_handlecrashitem(crashitem, report, sched):
    """
    Return the crashitem from pending and collection.
    """
    db = log_db(sched.config)
    reruns = db.get_test_reruns(crashitem)
    if db.get_test_failures(crashitem) < reruns:
        sched.mark_test_pending(crashitem)
        report.outcome = "rerun"

    db.add_test_failure(crashitem)


def pytest_runtest_protocol(item, nextitem):
    """
    Note: when teardown fails, two reports are generated for the case, one for
    the test case and the other for the teardown error.
    """
    reruns = get_reruns_count(item)
    if reruns is None:
        # global setting is not specified, and this test is not marked with
        # flaky
        return

    # while this doesn't need to be run with every item, it will fail on the
    # first item if necessary
    check_options(item.session.config)
    delay = get_reruns_delay(item)
    parallel = not is_master(item.config)
    item_location = item.location
    item_location_str = (item_location[0] + '::' + item_location[2]).replace('\\', '/')
    db = log_db(item.session.config)
    item.execution_count = db.get_test_failures(item_location_str)
    db.set_test_reruns(item_location_str, reruns)

    if item.execution_count > reruns:
        return True

    need_to_run = True
    while need_to_run:
        item.execution_count += 1
        item.ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)
        reports = runtestprotocol(item, nextitem=nextitem, log=False)

        for report in reports:  # 3 reports: setup, call, teardown
            report.rerun = item.execution_count - 1
            if _should_not_rerun(item, report, reruns):
                # last run or no failure detected, log normally
                item.ihook.pytest_runtest_logreport(report=report)
            else:
                # failure detected and reruns not exhausted, since i < reruns
                report.outcome = "rerun"
                time.sleep(delay)

                if not parallel or works_with_current_xdist():
                    # will rerun test, log intermediate result
                    item.ihook.pytest_runtest_logreport(report=report)

                # cleanin item's cashed results from any level of setups
                _remove_cached_results_from_failed_fixtures(item)
                _remove_failed_setup_state_from_session(item)

                break  # trigger rerun
        else:
            need_to_run = False

        item.ihook.pytest_runtest_logfinish(nodeid=item.nodeid, location=item.location)

    return True


def pytest_report_teststatus(report):
    """Adapted from https://pytest.org/latest/_modules/_pytest/skipping.html"""
    if report.outcome == "rerun":
        return "rerun", "R", ("RERUN", {"yellow": True})


def pytest_terminal_summary(terminalreporter):
    """Adapted from https://pytest.org/latest/_modules/_pytest/skipping.html"""
    tr = terminalreporter
    if not tr.reportchars:
        return

    lines = []
    for char in tr.reportchars:
        if char in "rR":
            show_rerun(terminalreporter, lines)

    if lines:
        tr._tw.sep("=", "rerun test summary info")
        for line in lines:
            tr._tw.line(line)


def show_rerun(terminalreporter, lines):
    rerun = terminalreporter.stats.get("rerun")
    if rerun:
        for rep in rerun:
            pos = rep.nodeid
            lines.append(f"RERUN {pos}")


if HAS_RESULTLOG:

    class RerunResultLog(ResultLog):
        def __init__(self, config, logfile):
            ResultLog.__init__(self, config, logfile)

        def pytest_runtest_logreport(self, report):
            """
            Adds support for rerun report fix for issue:
            https://github.com/pytest-dev/pytest-rerunfailures/issues/28
            """
            if report.when != "call" and report.passed:
                return
            res = self.config.hook.pytest_report_teststatus(report=report)
            code = res[1]
            if code == "x":
                longrepr = str(report.longrepr)
            elif code == "X":
                longrepr = ""
            elif report.passed:
                longrepr = ""
            elif report.failed:
                longrepr = str(report.longrepr)
            elif report.skipped:
                longrepr = str(report.longrepr[2])
            elif report.outcome == "rerun":
                longrepr = str(report.longrepr)
            else:
                longrepr = str(report.longrepr)

            self.log_outcome(report, code, longrepr)
