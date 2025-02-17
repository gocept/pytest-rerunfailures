import random
import time
from unittest import mock

import pytest

from pytest_rerunfailures import HAS_PYTEST_HANDLECRASHITEM

pytest_plugins = "pytester"

has_xdist = HAS_PYTEST_HANDLECRASHITEM


def temporary_failure(count=1):
    return f"""
            import py
            path = py.path.local(__file__).dirpath().ensure('test.res')
            count = path.read() or 1
            if int(count) <= {count}:
                path.write(int(count) + 1)
                raise Exception('Failure: {{0}}'.format(count))"""


def temporary_crash(count=1):
    return f"""
            import py
            import os
            path = py.path.local(__file__).dirpath().ensure('test.res')
            count = path.read() or 1
            if int(count) <= {count}:
                path.write(int(count) + 1)
                os._exit(1)"""


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
    field = "errors"
    check_outcome_field(outcomes, field, error)
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


def test_run_with_fail_on_flaky_fails_with_custom_error_code_after_pass_on_rerun(
    testdir,
):
    testdir.makepyfile(
        f"""
        def test_pass():
            {temporary_failure()}"""
    )
    result = testdir.runpytest("--reruns", "1", "--fail-on-flaky")
    assert_outcomes(result, passed=1, rerun=1)
    assert result.ret == 7


def test_run_fails_with_code_1_after_consistent_test_failure_even_with_fail_on_flaky(
    testdir,
):
    testdir.makepyfile("def test_fail(): assert False")
    result = testdir.runpytest("--reruns", "1", "--fail-on-flaky")
    assert_outcomes(result, passed=0, failed=1, rerun=1)
    assert result.ret == 1


def test_run_mark_and_fail_on_flaky_fails_with_custom_error_code_after_pass_on_rerun(
    testdir,
):
    testdir.makepyfile(f"""
        import pytest

        @pytest.mark.flaky(reruns=1)
        def test_fail():
            {temporary_failure()}
    """)
    result = testdir.runpytest("--fail-on-flaky")
    assert_outcomes(result, passed=1, rerun=1)
    assert result.ret == 7


def test_run_fails_with_code_1_after_test_failure_with_fail_on_flaky_and_mark(
    testdir,
):
    testdir.makepyfile("""
        import pytest

        @pytest.mark.flaky(reruns=2)
        def test_fail():
            assert False
    """)
    result = testdir.runpytest("--fail-on-flaky")
    assert_outcomes(result, passed=0, failed=1, rerun=2)
    assert result.ret == 1


def test_run_with_mark_and_fail_on_flaky_succeeds_if_all_tests_pass_without_reruns(
    testdir,
):
    testdir.makepyfile("""
        import pytest

        @pytest.mark.flaky(reruns=2)
        def test_marked_pass():
            assert True

        def test_unmarked_pass():
            assert True
    """)
    result = testdir.runpytest("--fail-on-flaky")
    assert_outcomes(result, passed=2, rerun=0)
    assert result.ret == pytest.ExitCode.OK


def test_run_with_fail_on_flaky_succeeds_if_all_tests_pass_without_reruns(
    testdir,
):
    testdir.makepyfile("def test_pass(): assert True")
    result = testdir.runpytest("--reruns", "1", "--fail-on-flaky")
    assert_outcomes(result, passed=1, rerun=0)
    assert result.ret == pytest.ExitCode.OK


@pytest.mark.skipif(not has_xdist, reason="requires xdist with crashitem")
def test_rerun_passes_after_temporary_test_crash(testdir):
    # note: we need two tests because there is a bug where xdist
    # cannot rerun the last test if it crashes. the bug exists only
    # in xdist is there is no error that causes the bug in this plugin.
    testdir.makepyfile(
        f"""
        def test_crash():
            {temporary_crash()}

        def test_pass():
            pass"""
    )
    result = testdir.runpytest("-p", "xdist", "-n", "1", "--reruns", "1", "-r", "R")
    assert_outcomes(result, passed=2, rerun=1)


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
    assert_outcomes(result, passed=1, rerun=2)


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
        rf"""
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


def test_no_rerun_on_strict_xfail_with_only_rerun_flag(testdir):
    testdir.makepyfile(
        """
        import pytest
        @pytest.mark.xfail(strict=True)
        def test_xfail():
            assert True
    """
    )
    result = testdir.runpytest("--reruns", "1", "--only-rerun", "RuntimeError")
    assert_outcomes(result, passed=0, failed=1, rerun=0)


@pytest.mark.parametrize(
    "rerun_except_texts, should_rerun",
    [
        (["AssertionError"], True),
        (["Assertion*"], True),
        (["Assertion"], True),
        (["ValueError"], False),
        (["AssertionError: "], True),
        (["ERR"], False),
        (["AssertionError", "OSError"], True),
        (["ValueError", "OSError"], False),
    ],
)
def test_rerun_except_flag(testdir, rerun_except_texts, should_rerun):
    testdir.makepyfile('def test_rerun_except(): raise ValueError("ERR")')

    num_failed = 1
    num_passed = 0
    num_reruns = 1
    num_reruns_actual = num_reruns if should_rerun else 0

    pytest_args = ["--reruns", str(num_reruns)]
    for rerun_except_text in rerun_except_texts:
        pytest_args.extend(["--rerun-except", rerun_except_text])
    result = testdir.runpytest(*pytest_args)
    assert_outcomes(
        result, passed=num_passed, failed=num_failed, rerun=num_reruns_actual
    )


@pytest.mark.parametrize(
    "only_rerun_texts, rerun_except_texts, should_rerun",
    [
        # Matches --only-rerun, but not --rerun-except (rerun)
        (["ValueError"], ["Not a Match"], True),
        (["ValueError", "AssertionError"], ["Not a match", "OSError"], True),
        # Matches --only-rerun AND --rerun-except (no rerun)
        (["ValueError"], ["ERR"], False),
        (["OSError", "ValueError"], ["Not a match", "ERR"], False),
        # Matches --rerun-except, but not --only-rerun (no rerun)
        (["OSError", "AssertionError"], ["TypeError", "ValueError"], False),
        # Matches neither --only-rerun nor --rerun-except (no rerun)
        (["AssertionError"], ["OSError"], False),
        # --rerun-except overrides --only-rerun for same arg (no rerun)
        (["ValueError"], ["ValueError"], False),
    ],
)
def test_rerun_except_and_only_rerun(
    testdir, rerun_except_texts, only_rerun_texts, should_rerun
):
    testdir.makepyfile('def test_only_rerun_except(): raise ValueError("ERR")')

    num_failed = 1
    num_passed = 0
    num_reruns = 1
    num_reruns_actual = num_reruns if should_rerun else 0

    pytest_args = ["--reruns", str(num_reruns)]
    for only_rerun_text in only_rerun_texts:
        pytest_args.extend(["--only-rerun", only_rerun_text])
    for rerun_except_text in rerun_except_texts:
        pytest_args.extend(["--rerun-except", rerun_except_text])
    result = testdir.runpytest(*pytest_args)
    assert_outcomes(
        result, passed=num_passed, failed=num_failed, rerun=num_reruns_actual
    )


def test_rerun_except_passes_setup_errors(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture()
        def fixture_setup_fails(non_existent_fixture):
            return 1

        def test_will_not_run(fixture_setup_fails):
            assert fixture_setup_fails == 1"""
    )

    num_reruns = 1
    pytest_args = ["--reruns", str(num_reruns), "--rerun-except", "ValueError"]
    result = testdir.runpytest(*pytest_args)
    assert result.ret != pytest.ExitCode.INTERNAL_ERROR
    assert_outcomes(result, passed=0, error=1, rerun=num_reruns)


@pytest.mark.parametrize(
    "condition, expected_reruns",
    [
        (1 == 1, 2),
        (1 == 2, 0),
        (True, 2),
        (False, 0),
        (1, 2),
        (0, 0),
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


@pytest.mark.parametrize(
    "condition, expected_reruns",
    [('sys.platform.startswith("non-exists") == False', 2), ("os.getpid() != -1", 2)],
)
# before evaluating the condition expression, sys&os&platform package has been imported
def test_reruns_with_string_condition(testdir, condition, expected_reruns):
    testdir.makepyfile(
        f"""
           import pytest

           @pytest.mark.flaky(reruns=2, condition='{condition}')
           def test_fail_two():
               assert False"""
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1, rerun=2)


def test_reruns_with_string_condition_with_global_var(testdir):
    testdir.makepyfile(
        """
              import pytest

              rerunBool = False
              @pytest.mark.flaky(reruns=2, condition='rerunBool')
              def test_fail_two():
                  global rerunBool
                  rerunBool = True
                  assert False"""
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1, rerun=2)


@pytest.mark.parametrize(
    "marker_only_rerun,cli_only_rerun,should_rerun",
    [
        ("AssertionError", None, True),
        ("AssertionError: ERR", None, True),
        (["AssertionError"], None, True),
        (["AssertionError: ABC"], None, False),
        ("ValueError", None, False),
        (["ValueError"], None, False),
        (["AssertionError", "ValueError"], None, True),
        # CLI override behavior
        ("AssertionError", "ValueError", True),
        ("ValueError", "AssertionError", False),
    ],
)
def test_only_rerun_flag_in_flaky_marker(
    testdir, marker_only_rerun, cli_only_rerun, should_rerun
):
    testdir.makepyfile(
        f"""
        import pytest

        @pytest.mark.flaky(reruns=1, only_rerun={marker_only_rerun!r})
        def test_fail():
            raise AssertionError("ERR")
        """
    )
    args = []
    if cli_only_rerun:
        args.extend(["--only-rerun", cli_only_rerun])
    result = testdir.runpytest()
    num_reruns = 1 if should_rerun else 0
    assert_outcomes(result, passed=0, failed=1, rerun=num_reruns)


@pytest.mark.parametrize(
    "marker_rerun_except,cli_rerun_except,raised_error,should_rerun",
    [
        ("AssertionError", None, "AssertionError", False),
        ("AssertionError: ERR", None, "AssertionError", False),
        (["AssertionError"], None, "AssertionError", False),
        (["AssertionError: ABC"], None, "AssertionError", True),
        ("ValueError", None, "AssertionError", True),
        (["ValueError"], None, "AssertionError", True),
        (["OSError", "ValueError"], None, "AssertionError", True),
        (["OSError", "AssertionError"], None, "AssertionError", False),
        # CLI override behavior
        ("AssertionError", "ValueError", "AssertionError", False),
        ("ValueError", "AssertionError", "AssertionError", True),
        ("CustomFailure", None, "CustomFailure", False),
        ("CustomFailure", None, "AssertionError", True),
    ],
)
def test_rerun_except_flag_in_flaky_marker(
    testdir, marker_rerun_except, cli_rerun_except, raised_error, should_rerun
):
    testdir.makepyfile(
        f"""
        import pytest

        class CustomFailure(Exception):
            pass

        @pytest.mark.flaky(reruns=1, rerun_except={marker_rerun_except!r})
        def test_fail():
            raise {raised_error}("ERR")
        """
    )
    args = []
    if cli_rerun_except:
        args.extend(["--rerun-except", cli_rerun_except])
    result = testdir.runpytest(*args)
    num_reruns = 1 if should_rerun else 0
    assert_outcomes(result, passed=0, failed=1, rerun=num_reruns)


def test_ini_file_parameters(testdir):
    testdir.makepyfile(
        """
        import time
        def test_foo():
            assert False
    """
    )
    testdir.makeini(
        """
        [pytest]
        reruns = 2
        reruns_delay = 3
    """
    )
    time.sleep = mock.MagicMock()
    result = testdir.runpytest()

    time.sleep.assert_called_with(3)
    assert_outcomes(result, passed=0, failed=1, rerun=2)


def test_ini_file_parameters_override(testdir):
    testdir.makepyfile(
        """
        import time
        def test_foo():
            assert False
    """
    )
    testdir.makeini(
        """
        [pytest]
        reruns = 2
        reruns_delay = 3
    """
    )
    time.sleep = mock.MagicMock()
    result = testdir.runpytest("--reruns", "4", "--reruns-delay", "5")

    time.sleep.assert_called_with(5)
    assert_outcomes(result, passed=0, failed=1, rerun=4)


def test_run_session_teardown_once_after_reruns(testdir):
    testdir.makepyfile(
        """
        import logging
        import pytest

        from unittest import TestCase

        @pytest.fixture(scope='session', autouse=True)
        def session_fixture():
            logging.info('session setup')
            yield
            logging.info('session teardown')

        @pytest.fixture(scope='class', autouse=True)
        def class_fixture():
            logging.info('class setup')
            yield
            logging.info('class teardown')

        @pytest.fixture(scope='function', autouse=True)
        def function_fixture():
            logging.info('function setup')
            yield
            logging.info('function teardown')

        @pytest.fixture(scope='function')
        def function_skip_fixture():
            logging.info('skip fixture setup')
            pytest.skip('some reason')
            yield
            logging.info('skip fixture teardown')

        @pytest.fixture(scope='function')
        def function_setup_fail_fixture():
            logging.info('fail fixture setup')
            assert False
            yield
            logging.info('fail fixture teardown')

        class TestFirstPassLastFail:

            @staticmethod
            def test_1():
                logging.info("TestFirstPassLastFail 1")

            @staticmethod
            def test_2():
                logging.info("TestFirstPassLastFail 2")
                assert False

        class TestFirstFailLastPass:

            @staticmethod
            def test_1():
                logging.info("TestFirstFailLastPass 1")
                assert False

            @staticmethod
            def test_2():
                logging.info("TestFirstFailLastPass 2")

        class TestSkipFirst:
            @staticmethod
            @pytest.mark.skipif(True, reason='Some reason')
            def test_1():
                logging.info("TestSkipFirst 1")
                assert False

            @staticmethod
            def test_2():
                logging.info("TestSkipFirst 2")
                assert False

        class TestSkipLast:
            @staticmethod
            def test_1():
                logging.info("TestSkipLast 1")
                assert False

            @staticmethod
            @pytest.mark.skipif(True, reason='Some reason')
            def test_2():
                logging.info("TestSkipLast 2")
                assert False

        class TestSkipFixture:
            @staticmethod
            def test_1(function_skip_fixture):
                logging.info("TestSkipFixture 1")

        class TestSetupFailed:
            @staticmethod
            def test_1(function_setup_fail_fixture):
                logging.info("TestSetupFailed 1")

        class TestTestCaseFailFirstFailLast(TestCase):

            @staticmethod
            def test_1():
                logging.info("TestTestCaseFailFirstFailLast 1")
                assert False

            @staticmethod
            def test_2():
                logging.info("TestTestCaseFailFirstFailLast 2")
                assert False

        class TestTestCaseSkipFirst(TestCase):

            @staticmethod
            @pytest.mark.skipif(True, reason='Some reason')
            def test_1():
                logging.info("TestTestCaseSkipFirst 1")
                assert False

            @staticmethod
            def test_2():
                logging.info("TestTestCaseSkipFirst 2")
                assert False

        class TestTestCaseSkipLast(TestCase):

            @staticmethod
            def test_1():
                logging.info("TestTestCaseSkipLast 1")
                assert False

            @staticmethod
            @pytest.mark.skipif(True, reason="Some reason")
            def test_2():
                logging.info("TestTestCaseSkipLast 2")
                assert False"""
    )
    import logging

    logging.info = mock.MagicMock()

    result = testdir.runpytest("--reruns", "2")
    expected_calls = [
        mock.call("session setup"),
        # TestFirstPassLastFail
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("TestFirstPassLastFail 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestFirstPassLastFail 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestFirstPassLastFail 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestFirstPassLastFail 2"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestFirstFailLastPass
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("TestFirstFailLastPass 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestFirstFailLastPass 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestFirstFailLastPass 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestFirstFailLastPass 2"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestSkipFirst
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("TestSkipFirst 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestSkipFirst 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestSkipFirst 2"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestSkipLast
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("TestSkipLast 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestSkipLast 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestSkipLast 1"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestSkipFixture
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("skip fixture setup"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestSetupFailed
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("fail fixture setup"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("fail fixture setup"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("fail fixture setup"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestTestCaseFailFirstFailLast
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("TestTestCaseFailFirstFailLast 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseFailFirstFailLast 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseFailFirstFailLast 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseFailFirstFailLast 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseFailFirstFailLast 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseFailFirstFailLast 2"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestTestCaseSkipFirst
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("TestTestCaseSkipFirst 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseSkipFirst 2"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseSkipFirst 2"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        # TestTestCaseSkipLast
        mock.call("class setup"),
        mock.call("function setup"),
        mock.call("TestTestCaseSkipLast 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseSkipLast 1"),
        mock.call("function teardown"),
        mock.call("function setup"),
        mock.call("TestTestCaseSkipLast 1"),
        mock.call("function teardown"),
        mock.call("class teardown"),
        mock.call("session teardown"),
    ]

    logging.info.assert_has_calls(expected_calls, any_order=False)
    assert_outcomes(result, failed=8, passed=2, rerun=18, skipped=5, error=1)


def test_exception_matches_rerun_except_query(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def session_fixture():
            print("session setup")
            yield "session"
            print("session teardown")

        @pytest.fixture(scope="package", autouse=True)
        def package_fixture():
            print("package setup")
            yield "package"
            print("package teardown")

        @pytest.fixture(scope="module", autouse=True)
        def module_fixture():
            print("module setup")
            yield "module"
            print("module teardown")

        @pytest.fixture(scope="class", autouse=True)
        def class_fixture():
            print("class setup")
            yield "class"
            print("class teardown")

        @pytest.fixture(scope="function", autouse=True)
        def function_fixture():
            print("function setup")
            yield "function"
            print("function teardown")

        @pytest.mark.flaky(reruns=1, rerun_except=["AssertionError"])
        class TestStuff:
            def test_1(self):
                raise AssertionError("fail")

            def test_2(self):
                assert False

    """
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=2, rerun=1)
    result.stdout.fnmatch_lines("session teardown")
    result.stdout.fnmatch_lines("package teardown")
    result.stdout.fnmatch_lines("module teardown")
    result.stdout.fnmatch_lines("class teardown")
    result.stdout.fnmatch_lines("function teardown")


def test_exception_not_match_rerun_except_query(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def session_fixture():
            print("session setup")
            yield "session"
            print("session teardown")

        @pytest.fixture(scope="function", autouse=True)
        def function_fixture():
            print("function setup")
            yield "function"
            print("function teardown")

        @pytest.mark.flaky(reruns=1, rerun_except="AssertionError")
        def test_1(session_fixture, function_fixture):
            raise ValueError("value")
    """
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1, rerun=1)
    result.stdout.fnmatch_lines("session teardown")


def test_exception_matches_only_rerun_query(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def session_fixture():
            print("session setup")
            yield "session"
            print("session teardown")

        @pytest.fixture(scope="function", autouse=True)
        def function_fixture():
            print("function setup")
            yield "function"
            print("function teardown")

        @pytest.mark.flaky(reruns=1, only_rerun=["AssertionError"])
        def test_1(session_fixture, function_fixture):
            raise AssertionError("fail")
    """
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1, rerun=1)
    result.stdout.fnmatch_lines("session teardown")


def test_exception_not_match_only_rerun_query(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def session_fixture():
            print("session setup")
            yield "session"
            print("session teardown")

        @pytest.fixture(scope="function", autouse=True)
        def function_fixture():
            print("function setup")
            yield "function"
            print("function teardown")

        @pytest.mark.flaky(reruns=1, only_rerun=["AssertionError"])
        def test_1(session_fixture, function_fixture):
            raise ValueError("fail")
    """
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1)
    result.stdout.fnmatch_lines("session teardown")


def test_exception_match_rerun_except_in_dual_query(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def session_fixture():
            print("session setup")
            yield "session"
            print("session teardown")

        @pytest.fixture(scope="function", autouse=True)
        def function_fixture():
            print("function setup")
            yield "function"
            print("function teardown")

        @pytest.mark.flaky(reruns=1, rerun_except=["Exception"], only_rerun=["Not"])
        def test_1(session_fixture, function_fixture):
            raise Exception("fail")
    """
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1)
    result.stdout.fnmatch_lines("session teardown")


def test_exception_match_only_rerun_in_dual_query(testdir):
    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture(scope="session", autouse=True)
        def session_fixture():
            print("session setup")
            yield "session"
            print("session teardown")

        @pytest.fixture(scope="function", autouse=True)
        def function_fixture():
            print("function setup")
            yield "function"
            print("function teardown")

        @pytest.mark.flaky(reruns=1, rerun_except=["Not"], only_rerun=["Exception"])
        def test_1(session_fixture, function_fixture):
            raise Exception("fail")
    """
    )
    result = testdir.runpytest()
    assert_outcomes(result, passed=0, failed=1, rerun=1)
    result.stdout.fnmatch_lines("session teardown")
