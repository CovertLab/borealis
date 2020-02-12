#!/bin/sh
# Rebuild the borealis pip package.

rm -rf dist build borealis_fireworks.egg-info
python setup.py sdist bdist_wheel --universal
