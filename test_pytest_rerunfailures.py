import random
import time
from unittest import mock

import pkg_resources
import pytest


pytest_plugins = "pytester"

PYTEST_GTE_61 = pkg_resources.parse_version(
    pytest.__version__
) >= pkg_resources.parse_version("6.1")


def temporary_failure(count=1):
    return f"""
            import py
            path = py.path.local(__file__).dirpath().ensure('test.res')
            count = path.read() or 1
            if int(count) <= {count}:
                path.write(int(count) + 1)
                raise Exception('Failure: {{0}}'.format(count))"""


def temporary_timeout(count=1):
    return f"""
            import py
            import time
            path = py.path.local(__file__).dirpath().ensure('test.res')
            count = path.read() or 1
            if int(count) <= {count}:
                path.write(int(count) + 1)
                time.sleep(15)"""


def check_outcome_field(outcomes, field_name, expected_value):
    field_value = outcomes.get(field_name, 0)
    assert field_value == expected_value, (
        f"outcomes.{field_name} has unexpected value. "
        f"Expected '{expected_value}' but got '{field_value}'"
    )


def assert_outcomes(
    result,
    passed=1,
    skipped=0,
    failed=0,
    error=0,
    xfailed=0,
    xpassed=0,
    rerun=0,
):
    outcomes = result.parseoutcomes()
    check_outcome_field(outcomes, "passed", passed)
    check_outcome_field(outcomes, "skipped", skipped)
    check_outcome_field(outcomes, "failed", failed)
    check_outcome_field(outcomes, "xfailed", xfailed)
    check_outcome_field(outcomes, "xpassed", xpassed)
    check_outcome_field(outcomes, "rerun", rerun)


def test_error_when_run_with_pdb(testdir):
    testdir.makepyfile("def test_pass(): pass")
    result = testdir.runpytest("--reruns", "1", "--pdb")
    result.stderr.fnmatch_lines_random("ERROR: --reruns incompatible with --pdb")


def test_no_rerun_on_pass(testdir):
    testdir.makepyfile("def test_pass(): pass")
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result)


def test_no_rerun_on_skipif_mark(testdir):
    reason = str(random.random())
    testdir.makepyfile(
        f"""
        import pytest
        @pytest.mark.skipif(reason='{reason}')
        def test_skip():
            pass
    """
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, skipped=1)


def test_no_rerun_on_skip_call(testdir):
    reason = str(random.random())
    testdir.makepyfile(
        f"""
        import pytest
        def test_skip():
            pytest.skip('{reason}')
    """
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, skipped=1)


def test_no_rerun_on_xfail_mark(testdir):
    testdir.makepyfile(
        """
        import pytest
        @pytest.mark.xfail()
        def test_xfail():
            assert False
    """
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, xfailed=1)


def test_no_rerun_on_xfail_call(testdir):
    reason = str(random.random())
    testdir.makepyfile(
        f"""
        import pytest
        def test_xfail():
            pytest.xfail('{reason}')
    """
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, xfailed=1)


def test_no_rerun_on_xpass(testdir):
    testdir.makepyfile(
        """
        import pytest
        @pytest.mark.xfail()
        def test_xpass():
            pass
    """
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, xpassed=1)


def test_rerun_fails_after_consistent_setup_failure(testdir):
    testdir.makepyfile("def test_pass(): pass")
    testdir.makeconftest(
        """
        def pytest_runtest_setup(item):
            raise Exception('Setup failure')"""
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, error=1, rerun=1)


def test_rerun_passes_after_temporary_setup_failure(testdir):
    testdir.makepyfile("def test_pass(): pass")
    testdir.makeconftest(
        f"""
        def pytest_runtest_setup(item):
            {temporary_failure()}"""
    )
    result = testdir.runpytest("--reruns", "1", "-r", "R")
    assert_outcomes(result, passed=1, rerun=1)


def test_rerun_fails_after_consistent_test_failure(testdir):
    testdir.makepyfile("def test_fail(): assert False")
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, failed=1, rerun=1)


def test_rerun_passes_after_temporary_test_failure(testdir):
    testdir.makepyfile(
        f"""
        def test_pass():
            {temporary_failure()}"""
    )
    result = testdir.runpytest("--reruns", "1", "-r", "R")
    assert_outcomes(result, passed=1, rerun=1)


def test_rerun_passes_after_temporary_test_timeout(testdir):
    testdir.makepyfile(
        f"""
        def test_pass():
            {temporary_timeout()}"""
    )
    result = testdir.runpytest("--reruns", "1", "-r", "R", "--timeout", "10")
    assert_outcomes(result, passed=1, rerun=1)


def test_rerun_passes_after_temporary_test_failure_with_flaky_mark(testdir):
    testdir.makepyfile(
        f"""
        import pytest
        @pytest.mark.flaky(reruns=2)
        def test_pass():
            {temporary_failure(2)}"""
    )
    result = testdir.runpytest("-r", "R")
    assert_outcomes(result, passed=1, rerun=2)


def test_reruns_if_flaky_mark_is_called_without_options(testdir):
    testdir.makepyfile(
        f"""
        import pytest
        @pytest.mark.flaky()
        def test_pass():
            {temporary_failure(1)}"""
    )
    result = testdir.runpytest("-r", "R")
    assert_outcomes(result, passed=1, rerun=1)


def test_reruns_if_flaky_mark_is_called_with_positional_argument(testdir):
    testdir.makepyfile(
        f"""
        import pytest
        @pytest.mark.flaky(2)
        def test_pass():
            {temporary_failure(2)}"""
    )
    result = testdir.runpytest("-r", "R")
    assert_outcomes(result, passed=1, rerun=2)


def test_no_extra_test_summary_for_reruns_by_default(testdir):
    testdir.makepyfile(
        f"""
        def test_pass():
            {temporary_failure()}"""
    )
    result = testdir.runpytest("--reruns", "1")
    assert "RERUN" not in result.stdout.str()
    assert "1 rerun" in result.stdout.str()


def test_extra_test_summary_for_reruns(testdir):
    testdir.makepyfile(
        f"""
        def test_pass():
            {temporary_failure()}"""
    )
    result = testdir.runpytest("--reruns", "1", "-r", "R")
    result.stdout.fnmatch_lines_random(["RERUN test_*:*"])
    assert "1 rerun" in result.stdout.str()


def test_verbose(testdir):
    testdir.makepyfile(
        f"""
        def test_pass():
            {temporary_failure()}"""
    )
    result = testdir.runpytest("--reruns", "1", "-v")
    result.stdout.fnmatch_lines_random(["test_*:* RERUN*"])
    assert "1 rerun" in result.stdout.str()


def test_no_rerun_on_class_setup_error_without_reruns(testdir):
    testdir.makepyfile(
        """
        class TestFoo(object):
            @classmethod
            def setup_class(cls):
                assert False

            def test_pass():
                pass"""
    )
    result = testdir.runpytest("--reruns", "0")
    assert_outcomes(result, passed=0, error=1, rerun=0)


def test_rerun_on_class_setup_error_with_reruns(testdir):
    testdir.makepyfile(
        """
        class TestFoo(object):
            @classmethod
            def setup_class(cls):
                assert False

            def test_pass():
                pass"""
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=0, error=1, rerun=1)


@pytest.mark.skipif(PYTEST_GTE_61, reason="--result-log removed in pytest>=6.1")
def test_rerun_with_resultslog(testdir):
    testdir.makepyfile(
        """
        def test_fail():
            assert False"""
    )

    result = testdir.runpytest("--reruns", "2", "--result-log", "./pytest.log")

    assert_outcomes(result, passed=0, failed=1, rerun=2)


@pytest.mark.parametrize("delay_time", [-1, 0, 0.0, 1, 2.5])
def test_reruns_with_delay(testdir, delay_time):
    testdir.makepyfile(
        """
        def test_fail():
            assert False"""
    )

    time.sleep = mock.MagicMock()

    result = testdir.runpytest("--reruns", "3", "--reruns-delay", str(delay_time))

    if delay_time < 0:
        result.stdout.fnmatch_lines(
            "*UserWarning: Delay time between re-runs cannot be < 0. "
            "Using default value: 0"
        )
        delay_time = 0

    time.sleep.assert_called_with(delay_time)

    assert_outcomes(result, passed=0, failed=1, rerun=3)


@pytest.mark.parametrize("delay_time", [-1, 0, 0.0, 1, 2.5])
def test_reruns_with_delay_marker(testdir, delay_time):
    testdir.makepyfile(
        f"""
        import pytest

        @pytest.mark.flaky(reruns=2, reruns_delay={delay_time})
        def test_fail_two():
            assert False"""
    )

    time.sleep = mock.MagicMock()

    result = testdir.runpytest()

    if delay_time < 0:
        result.stdout.fnmatch_lines(
            "*UserWarning: Delay time between re-runs cannot be < 0. "
            "Using default value: 0"
        )
        delay_time = 0

    time.sleep.assert_called_with(delay_time)

    assert_outcomes(result, passed=0, failed=1, rerun=2)


def test_rerun_on_setup_class_with_error_with_reruns(testdir):
    """
    Case: setup_class throwing error on the first execution for parametrized test
    """
    testdir.makepyfile(
        """
        import pytest

        pass_fixture = False

        class TestFoo(object):
            @classmethod
            def setup_class(cls):
                global pass_fixture
                if not pass_fixture:
                    pass_fixture = True
                    assert False
                assert True
            @pytest.mark.parametrize('param', [1, 2, 3])
            def test_pass(self, param):
                assert param"""
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=3, rerun=1)


def test_rerun_on_class_scope_fixture_with_error_with_reruns(testdir):
    """
    Case: Class scope fixture throwing error on the first execution
    for parametrized test
    """
    testdir.makepyfile(
        """
        import pytest

        pass_fixture = False

        class TestFoo(object):

            @pytest.fixture(scope="class")
            def setup_fixture(self):
                global pass_fixture
                if not pass_fixture:
                    pass_fixture = True
                    assert False
                assert True
            @pytest.mark.parametrize('param', [1, 2, 3])
            def test_pass(self, setup_fixture, param):
                assert param"""
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=3, rerun=1)


def test_rerun_on_module_fixture_with_reruns(testdir):
    """
    Case: Module scope fixture is not re-executed when class scope fixture throwing
    error on the first execution for parametrized test
    """
    testdir.makepyfile(
        """
        import pytest

        pass_fixture = False

        @pytest.fixture(scope='module')
        def module_fixture():
            assert not pass_fixture

        class TestFoo(object):
            @pytest.fixture(scope="class")
            def setup_fixture(self):
                global pass_fixture
                if not pass_fixture:
                    pass_fixture = True
                    assert False
                assert True
            def test_pass_1(self, module_fixture, setup_fixture):
                assert True

            def test_pass_2(self, module_fixture, setup_fixture):
                assert True"""
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=2, rerun=1)


def test_rerun_on_session_fixture_with_reruns(testdir):
    """
    Case: Module scope fixture is not re-executed when class scope fixture
    throwing error on the first execution for parametrized test
    """
    testdir.makepyfile(
        """
        import pytest

        pass_fixture = False

        @pytest.fixture(scope='session')
        def session_fixture():
            assert not pass_fixture

        class TestFoo(object):
            @pytest.fixture(scope="class")
            def setup_fixture(self):
                global pass_fixture
                if not pass_fixture:
                    pass_fixture = True
                    assert False
                assert True

            def test_pass_1(self, session_fixture, setup_fixture):
                assert True
            def test_pass_2(self, session_fixture, setup_fixture):
                assert True"""
    )
    result = testdir.runpytest("--reruns", "1")
    assert_outcomes(result, passed=2, rerun=1)


def test_execution_count_exposed(testdir):
    testdir.makepyfile("def test_pass(): assert True")
    testdir.makeconftest(
        """
        def pytest_runtest_teardown(item):
            assert item.execution_count == 3"""
    )
    result = testdir.runpytest("--reruns", "2")
    assert_outcomes(result, passed=3, rerun=2)


def test_rerun_report(testdir):
    testdir.makepyfile("def test_pass(): assert False")
    testdir.makeconftest(
        """
        def pytest_runtest_logreport(report):
            assert hasattr(report, 'rerun')
            assert isinstance(report.rerun, int)
            assert report.rerun <= 2
        """
    )
    result = testdir.runpytest("--reruns", "2")
    assert_outcomes(result, failed=1, rerun=2, passed=0)


def test_pytest_runtest_logfinish_is_called(testdir):
    hook_message = "Message from pytest_runtest_logfinish hook"
    testdir.makepyfile("def test_pass(): pass")
    testdir.makeconftest(
        fr"""
        def pytest_runtest_logfinish(nodeid, location):
            print("\n{hook_message}\n")
    """
    )
    result = testdir.runpytest("--reruns", "1", "-s")
    result.stdout.fnmatch_lines(hook_message)


@pytest.mark.parametrize(
    "only_rerun_texts, should_rerun",
    [
        (["AssertionError"], True),
        (["Assertion*"], True),
        (["Assertion"], True),
        (["ValueError"], False),
        ([""], True),
        (["AssertionError: "], True),
        (["AssertionError: ERR"], True),
        (["ERR"], True),
        (["AssertionError,ValueError"], False),
        (["AssertionError ValueError"], False),
        (["AssertionError", "ValueError"], True),
    ],
)
def test_only_rerun_flag(testdir, only_rerun_texts, should_rerun):
    testdir.makepyfile('def test_only_rerun(): raise AssertionError("ERR")')

    num_failed = 1
    num_passed = 0
    num_reruns = 1
    num_reruns_actual = num_reruns if should_rerun else 0

    pytest_args = ["--reruns", str(num_reruns)]
    for only_rerun_text in only_rerun_texts:
        pytest_args.extend(["--only-rerun", only_rerun_text])
    result = testdir.runpytest(*pytest_args)
    assert_outcomes(
        result, passed=num_passed, failed=num_failed, rerun=num_reruns_actual
    )


@pytest.mark.parametrize(
    "condition, expected_reruns",
    [
        (1 == 1, 2),
        (1 == 2, 0),
        (True, 2),
        (False, 0),
        (1, 2),
        (0, 0),
        ("'non-empty'", 2),
        ("''", 0),
        (["list"], 2),
        ([], 0),
        ({"dict": 1}, 2),
        ({}, 0),
        (None, 0),
    ],
)
def test_reruns_with_condition_marker(testdir, condition, expected_reruns):
    testdir.makepyfile(
        f"""
        import pytest

        @pytest.mark.flaky(reruns=2, condition={condition})
        def test_fail_two():
            assert False"""
    )

    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1, rerun=expected_reruns)
