from setuptools import setup

with open("README.rst") as readme, open("CHANGES.rst") as changelog:
    long_description = ".. contents::\n\n" + readme.read() + "\n\n" + changelog.read()

setup(
    name="pytest-rerunfailures",
    version="9.2.dev0",
    description="pytest plugin to re-run tests to eliminate flaky failures",
    long_description=long_description,
    author="Leah Klearman",
    author_email="lklrmn@gmail.com",
    url="https://github.com/pytest-dev/pytest-rerunfailures",
    py_modules=["pytest_rerunfailures"],
    entry_points={"pytest11": ["rerunfailures = pytest_rerunfailures"]},
    install_requires=["setuptools>=40.0", "pytest >= 5.0", "sqlitedict"],
    python_requires=">=3.6",
    license="Mozilla Public License 2.0 (MPL 2.0)",
    keywords="py.test pytest rerun failures flaky",
    zip_safe=False,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Framework :: Pytest",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS :: MacOS X",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Testing",
        "Topic :: Utilities",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
)
