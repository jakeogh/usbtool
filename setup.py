# -*- coding: utf-8 -*-

from setuptools import find_packages
from setuptools import setup

import fastentrypoints

dependencies = [
    "click",
    "asserttool @ git+https://git@github.com/jakeogh/asserttool",
    "serialtool @ git+https://git@github.com/jakeogh/serialtool",
    "timetool @ git+https://git@github.com/jakeogh/timetool",
]

config = {
    "version": "0.1",
    "name": "usbtool",
    "url": "https://github.com/jakeogh/usbtool",
    "license": "ISC",
    "author": "Justin Keogh",
    "author_email": "github.com@v6y.net",
    "description": "lookup usb tty device path by device id",
    "long_description": __doc__,
    "packages": find_packages(exclude=["tests"]),
    "package_data": {"usbtool": ["py.typed"]},
    "include_package_data": True,
    "zip_safe": False,
    "platforms": "any",
    "install_requires": dependencies,
    "entry_points": {
        "console_scripts": [
            "usbtool=usbtool.usbtool:cli",
        ],
    },
}

setup(**config)
