#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='factorio-mod-manager',
    version='0.1.0',
    packages=find_packages(),
    install_requires=['requests'],
    py_modules=['resolver'],
    scripts=["fmm.py"],
)
