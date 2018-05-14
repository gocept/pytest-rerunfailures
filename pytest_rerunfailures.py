import pkg_resources
import time
import warnings

import pytest

from _pytest.runner import runtestprotocol
from _pytest.resultlog import ResultLog


def works_with_current_xdist():
    """
    Pytest hook

    Returns compatibility with installed pytest-xdist version.

    When running tests in parallel using pytest-xdist < 1.20.0, the first
    report that is logged will finish and terminate the current node rather
    rerunning the test. Thus we must skip logging of intermediate results under
    these circumstances, otherwise no test is rerun.

    Returns
    -------
    result : bool || None
    """
    try:
        d = pkg_resources.get_distribution('pytest-xdist')
        return d.parsed_version >= pkg_resources.parse_version('1.20')
    except pkg_resources.DistributionNotFound:
        return None


def check_options(config):
    """
    Making sure the options make sense
    should run before / at the begining of pytest_cmdline_main

    Parameters
    ----------
    config : _pytest.config.Config
    """
    val = config.getvalue
    if not val("collectonly"):
        if config.option.reruns != 0:
            if config.option.usepdb:   # a core option
                raise pytest.UsageError("--reruns incompatible with --pdb")


def pytest_addoption(parser):
    """
    Added rerunfailed related flags to pytest_addoption hook

    Parameters
    ----------
    parser : _pytest.config.Parser
    """
    group = parser.getgroup(
        "rerunfailures",
        "re-run failing tests with fixtures invalidation to eliminate flaky failures")
    group._addoption(
        '--reruns',
        action="store",
        dest="reruns",
        type=int,
        default=0,
        help="number of times to re-run failed tests. defaults to 0.")
    group._addoption(
        '--reruns-delay',
        action='store',
        dest='reruns_delay',
        type=float,
        default=0,
        help='add time (seconds) delay between reruns.'
    )


def pytest_configure(config):
    """
    Defined appropriate plugins selection in pytest_configure hook

    Parameters
    ----------
    config : _pytest.config.Config
    """
    config.addinivalue_line(
        "markers", "flaky(reruns=1, reruns_delay=0): mark test to re-run up "
                   "to 'reruns' times. Add a delay of 'reruns_delay' seconds "
                   "between re-runs.")

    check_options(config)

    plugin = RerunPlugin()
    config.pluginmanager.register(plugin, 'RerunPlugin')

    resultlog = getattr(config, '_resultlog', None)
    if resultlog:
        logfile = resultlog.logfile
        config.pluginmanager.unregister(resultlog)
        config._resultlog = RerunResultLog(config, logfile)
        config.pluginmanager.register(config._resultlog)


class RerunPlugin(object):
    """Pytest plugin implements rerun failed functionality"""

    def __init__(self):
        self.tests_to_rerun = set([])

    def pytest_runtest_protocol(self, item, nextitem):
        """
        Pytest hook

        Note: when teardown fails, two reports are generated for the case, one for
        the test case and the other for the teardown error.

        Parameters
        ----------
        item : _pytest.main.Item
        nextitem : _pytest.main.Item || None
        """
        item.ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)
        reports = runtestprotocol(item, nextitem=nextitem, log=False)

        for report in reports:  # 3 reports: setup, test, teardown
            xfail = hasattr(report, 'wasxfail')
            if report.failed and not xfail:
                # failure detected
                self.tests_to_rerun.add(item)
                report.outcome = 'rerun'

            item.ihook.pytest_runtest_logreport(report=report)

        # Last test of a testrun was performed
        if nextitem == None:
            self._execute_reruns()

        return True

    def _execute_reruns(self):
        """
        Perform reruns for failed tests
        """
        for item in self.tests_to_rerun:
            reruns = self._get_reruns_count(item)
            if reruns is None:
                continue

            self._rerun_item(item, reruns)


    def _rerun_item(self, item, reruns):
        """
        Perform reruns for single test items

        Parameters
        ----------
        item : _pytest.main.Item
        """
        delay = self._get_reruns_delay(item)
        parallel = hasattr(item.config, 'slaveinput')

        for i in range(reruns):
            self._invalidate_fixtures(item)
            time.sleep(delay)
            item.ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)
            reports = runtestprotocol(item, nextitem=None, log=False)
            rerun_status = True
            for report in reports:
                xfail = hasattr(report, 'wasxfail')
                report.rerun = i
                rerun_status = rerun_status and (not report.failed or xfail)
                if report.failed and (i != reruns - 1):
                    report.outcome = 'rerun'
                if not parallel or works_with_current_xdist():
                    # will log intermediate result
                    item.ihook.pytest_runtest_logreport(report=report)

            if rerun_status:
                break

    def _invalidate_fixtures(self, item):
        """
        Invalidate fixtures related to test item

        Parameters
        ----------
        item : _pytest.main.Item
        """
        # collect all item related fixtures and call finalizers for them
        fixturemanager = item.session._fixturemanager
        fixtures = set(item.fixturenames)
        fixtures.update(fixturemanager._getautousenames(item.nodeid))
        fixtures.update(item._fixtureinfo.argnames)
        usefixtures = getattr(item.function, 'usefixtures', None)
        if usefixtures:
            fixtures.update(usefixtures.args)

        for fixt in fixtures:
            for fixtdef in fixturemanager.getfixturedefs(fixt, item.nodeid) or []:
                item._initrequest()
                fixtdef.finish(item._request)

    def pytest_report_teststatus(self, report):
        """
        Pytest hook

        Handle of report rerun outcome
        Adapted from https://docs.pytest.org/en/latest/skipping.html

        Parameters
        ----------
        report : _pytest.runner.TestReport
        """
        if report.outcome == 'rerun':
            return 'rerun', 'R', ('RERUN', {'yellow': True})

    def pytest_terminal_summary(self, terminalreporter):
        """
        Pytest hook

        Handle rerun terminal summary report
        Adapted from https://docs.pytest.org/en/latest/skipping.html

        Parameters
        ----------
        terminalreporter : _pytest.terminal.TerminalReporter
        """
        tr = terminalreporter
        if not tr.reportchars:
            return

        lines = []
        for char in tr.reportchars:
            if char in 'rR':
                self._show_rerun(terminalreporter, lines)

        if lines:
            tr._tw.sep("=", "rerun test summary info")
            for line in lines:
                tr._tw.line(line)

    def _show_rerun(self, terminalreporter, lines):
        """
        Format reruned tests to be market as RERUN in output
        Adapted from https://docs.pytest.org/en/latest/skipping.html

        Parameters
        ----------
        terminalreporter : _pytest.terminal.TerminalReporter
        lines : list[Item]
        """
        rerun = terminalreporter.stats.get("rerun")
        if rerun:
            for rep in rerun:
                pos = rep.nodeid
                lines.append("RERUN %s" % (pos,))

    def _get_reruns_count(self, item):
        """
        Retrive amount of reruns setuped for test item

        Parameters
        ----------
        item : _pytest.main.Item

        Returns
        -------
        reruns : int
        """
        rerun_marker = item.get_marker("flaky")
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

    def _get_reruns_delay(self, item):
        """
        Retrive rerun delay setuped for test item

        Parameters
        ----------
        item : _pytest.main.Item

        Returns
        -------
        reruns : int
        """
        rerun_marker = item.get_marker("flaky")

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
            warnings.warn('Delay time between re-runs cannot be < 0. '
                        'Using default value: 0')

        return delay


class RerunResultLog(ResultLog):
    """ResultLog wrapper for support rerun capabilities"""

    def __init__(self, config, logfile):
        ResultLog.__init__(self, config, logfile)

    def pytest_runtest_logreport(self, report):
        """
        Pytest hook

        Adds support for rerun report fix for issue:
        https://github.com/pytest-dev/pytest-rerunfailures/issues/28

        Parameters
        ----------
        report : _pytest.runner.TestReport
        """
        if report.when != "call" and report.passed:
            return
        res = self.config.hook.pytest_report_teststatus(report=report)
        code = res[1]
        if code == 'x':
            longrepr = str(report.longrepr)
        elif code == 'X':
            longrepr = ''
        elif report.passed:
            longrepr = ""
        elif report.failed:
            longrepr = str(report.longrepr)
        elif report.skipped:
            longrepr = str(report.longrepr[2])
        elif report.outcome == 'rerun':
            longrepr = str(report.longrepr)

        self.log_outcome(report, code, longrepr)
