Changelog
=========

10.0 (unreleased)
-----------------

Backwards incompatible changes
++++++++++++++++++++++++++++++

- Drop support for Python 3.5.

Other changes
+++++++++++++

- Check for the resultlog by feature and not by version as pytest master does
  not provide a consistent version.


9.1.1 (2020-09-29)
------------------

Compatibility fix.
++++++++++++++++++

- Ignore ``--result-log`` command line option when used together with ``pytest
  >= 6.1.0``, as it was removed there. This is a quick fix, use an older
  version of pytest, if you want to keep this feature for now.
  (Thanks to `@ntessore`_ for the PR)

- Support up to pytest 6.1.0.

.. _@ntessore: https://github.com/ntessore


9.1 (2020-08-26)
----------------

Features
++++++++

- Add a new flag ``--only-rerun`` to allow for users to rerun only certain
  errors.

Other changes
+++++++++++++

- Drop dependency on ``mock``.

- Add support for pre-commit and add a linting tox target.
  (`#117 <https://github.com/pytest-dev/pytest-rerunfailures/pull/117>`_)
  (PR from `@gnikonorov`_)

- Ensure ``pytest_runtest_logreport`` is called for all reports in a test.
  (`#108 <https://github.com/pytest-dev/pytest-rerunfailures/issues/108>`_)
  (PR from `@gnikonorov`_)

.. _@gnikonorov: https://github.com/gnikonorov


9.0 (2020-03-18)
----------------

Backwards incompatible changes
++++++++++++++++++++++++++++++

- Drop support for pytest version 4.4, 4.5 and 4.6.

- Drop support for Python 2.7.


Features
++++++++

- Add support for pytest 5.4.

- Add support for Python 3.8.


8.0 (2019-11-18)
----------------

Backwards incompatible changes
++++++++++++++++++++++++++++++

- Drop support for pytest version 3.10, 4.0, 4.1, 4.2 and 4.3

- Drop support for Python 3.4.

Features
++++++++

- Add support for pytest version 4.4, 4.5, 4.6, 5.0, 5.1 and 5.2.

Bug fixes
+++++++++

- Explicitly depend on setuptools to ensure installation when working in
  environments without it.
  (`#98 <https://github.com/pytest-dev/pytest-rerunfailures/pull/98>`_)
  (PR from `@Eric-Arellano`_)

.. _@Eric-Arellano: https://github.com/Eric-Arellano


7.0 (2019-03-28)
----------------

Backwards incompatible changes
++++++++++++++++++++++++++++++

- Drop support for pytest version 3.8 and 3.9.

Features
++++++++

- Add support for pytest version 4.2 and 4.3.

Bug fixes
+++++++++

- Fixed #83 issue about ignored ``pytest_runtest_logfinish`` hooks.
  (`#83 <https://github.com/pytest-dev/pytest-rerunfailures/issues/83>`_)
  (PR from `@KillAChicken`_)

.. _@KillAChicken: https://github.com/KillAChicken


6.0 (2019-01-08)
----------------

Backwards incompatible changes
++++++++++++++++++++++++++++++

- Drop support for pytest version 3.6 and 3.7.

Features
++++++++

- Add support for pytest version 4.0 and 4.1.

Bug fixes
+++++++++

- Fixed #77 regression issue introduced in 4.2 related to the ``rerun``
  attribute on the test report.
  (`#77 <https://github.com/pytest-dev/pytest-rerunfailures/issues/77>`_)
  (Thanks to `@RibeiroAna`_ for the PR).

.. _@RibeiroAna: https://github.com/RibeiroAna


5.0 (2018-11-06)
----------------

- Drop support for pytest versions < 3.6 to reduce the maintenance burden.

- Add support up to pytest version 3.10. Thus supporting the newest 5 pytest
  releases.

- Add support for Python 3.7.

- Fix issue can occur when used together with `pytest-flake8`
  (`#73 <https://github.com/pytest-dev/pytest-rerunfailures/issues/73>`_)


4.2 (2018-10-04)
----------------

- Fixed #64 issue related to ``setup_class`` and ``fixture`` executions on rerun (Thanks to
  `@OlegKuzovkov`_ for the PR).

- Added new ``execution_count`` attribute to reflect the number of test case executions according to #67 issue.
  (Thanks to `@OlegKuzovkov`_ for the PR).

.. _@OlegKuzovkov: https://github.com/OlegKuzovkov


4.1 (2018-05-23)
----------------

- Add support for pytest 3.6 by using ``Node.get_closest_marker()`` (Thanks to
  `@The-Compiler`_ for the PR).

.. _@The-Compiler: https://github.com/The-Compiler

4.0 (2017-12-23)
----------------

- Added option to add a delay time between test re-runs (Thanks to `@Kanguros`_
  for the PR).

- Added support for pytest >= 3.3.

- Drop support for pytest < 2.8.7.

.. _@Kanguros: https://github.com/Kanguros


3.1 (2017-08-29)
----------------

- Restored compatibility with pytest-xdist. (Thanks to `@davehunt`_ for the PR)

.. _@davehunt: https://github.com/davehunt


3.0 (2017-08-17)
----------------

- Add support for Python 3.6.

- Add support for pytest 2.9 up to 3.2

- Drop support for Python 2.6 and 3.3.

- Drop support for pytest < 2.7.


2.2 (2017-06-23)
----------------

- Ensure that other plugins can run after this one, in case of a global setting
  ``--rerun=0``. (Thanks to `@sublee`_ for the PR)

.. _@sublee: https://github.com/sublee

2.1.0 (2016-11-01)
------------------

- Add default value of ``reruns=1`` if ``pytest.mark.flaky()`` is called
  without arguments.

- Also offer a distribution as universal wheel. (Thanks to `@tltx`_ for the PR)

.. _@tltx: https://github.com/tltx


2.0.1 (2016-08-10)
-----------------------------

- Prepare CLI options to pytest 3.0, to avoid a deprecation warning.

- Fix error due to missing CHANGES.rst when creating the source distribution
  by adding a MANIFEST.in.


2.0.0 (2016-04-06)
------------------

- Drop support for Python 3.2, since supporting it became too much of a hassle.
  (Reason: Virtualenv 14+ / PIP 8+ do not support Python 3.2 anymore.)


1.0.2 (2016-03-29)
------------------

- Add support for `--resultlog` option by parsing reruns accordingly. (#28)


1.0.1 (2016-02-02)
------------------

- Improve package description and include CHANGELOG into description.


1.0.0 (2016-02-02)
------------------

- Rewrite to use newer API of pytest >= 2.3.0

- Improve support for pytest-xdist by only logging the final result.
  (Logging intermediate results will finish the test rather rerunning it.)
