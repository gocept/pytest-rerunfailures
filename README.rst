pytest-rerunfailures
====================

pytest-rerunfailures is a plugin for `py.test <http://pytest.org>`_ that
re-runs tests to eliminate intermittent failures with failed tests related fixture invalidation.
Added all scoped fixtures invalidation for current test item in case of test failure before rerun occurs.
Plugin able to track all related fixtures: direct injects, autouse, usefixture mark.
Fixtures invalidated gracefully with executing finalizer.
All reruns schedule to be executed at testrun end

Requirements
------------

You will need the following prerequisites in order to use pytest-rerunfailures:

- Python 2.7, 3.4, 3.5, 3.6, PyPy, or PyPy3
- pytest 2.8.7 or newer

Installation
------------

To install pytest-rerunfailures:

.. code-block:: bash

  $ pip install pytest-rerunfailures

Re-run all failures
-------------------

To re-run all test failures, use the ``--reruns`` command line option with the
maximum number of times you'd like the tests to run:

.. code-block:: bash

  $ pytest --reruns 5

To add a delay time between re-runs use the ``--reruns-delay`` command line
option with the amount of seconds that you would like wait before the next
test re-run is launched:

.. code-block:: bash

   $ pytest --reruns 5 --reruns-delay 1

Re-run individual failures
--------------------------

To mark individual tests as flaky, and have them automatically re-run when they
fail, add the ``flaky`` mark with the maximum number of times you'd like the
test to run:

.. code-block:: python

  @pytest.mark.flaky(reruns=5)
  def test_example():
      import random
      assert random.choice([True, False])

Note that when teardown fails, two reports are generated for the case, one for
the test case and the other for the teardown error.

You can also specify the re-run delay time in the marker:

.. code-block:: python

  @pytest.mark.flaky(reruns=5, reruns_delay=2)
  def test_example():
      import random
      assert random.choice([True, False])

Output
------

Here's an example of the output provided by the plugin when run with
``--reruns 2`` and ``-r aR``::

  test_report.py RRF

  ================================== FAILURES ==================================
  __________________________________ test_fail _________________________________

      def test_fail():
  >       assert False
  E       assert False

  test_report.py:9: AssertionError
  ============================ rerun test summary info =========================
  RERUN test_report.py::test_fail
  RERUN test_report.py::test_fail
  ============================ short test summary info =========================
  FAIL test_report.py::test_fail
  ======================= 1 failed, 2 rerun in 0.02 seconds ====================

Note that output will show all re-runs. Tests that fail on all the re-runs will
be marked as failed.

Persist rerun stats
-------------------
Plugin provide ability to store rerun stats to standalone json file:
  ``--reruns-artifact-path {path-to-json}``

Stats file fill consist next fields::

  total_reruns - total rerun performed
  total_failed - total tests failed during run
  total_resolved_by_reruns - amount of tests fixed by rerun
  rerun_tests - List of each test rerun
    nodeid - pytest test nodeid
    status - test status after rerun: flake or failed
    rerun_trace - Test relevant tarces for teardown, setup and test call
    original_trace - Original test failure tarce appreared during main run 

Skip reruns execution
---------------------
In case if it is not needed to perform reruns if many tests failed next param could be used:
  ``--max-tests-rerun {threshold}``
So if during testrun will occur more failed test then threshold value no reruns would be performed.

Compatibility
-------------

* This plugin is *not* compatible with pytest-xdist's --looponfail flag.
* This plugin is *not* compatible with the core --pdb flag.

Releasing
---------


Update [CHANGES.rst](CHANGES.rst) to make sure changelog is updated for the new version.

Update package version in [setup.py](setup.py).

Tag version with a semver like `v4.1.10` and jarvis will package and upload it to artifactory

Resources
---------

- `Issue Tracker <https://github.com/datarobot/pytest-rerunfailures>`_
- `Code <https://github.com/datarobot/pytest-rerunfailures>`_
