#!/bin/sh
# Clean out then build the borealis pip package.

set -eu

# 1. Manually update the version number in the setup.py file.

# 2. Clean out the old build products.
rm -rf dist build borealis_fireworks.egg-info

# 3. Build source-distribution and binary-distribution packages.
python setup.py sdist bdist_wheel --universal

# 4. Test it locally.

# 5. Manually upload the package per
# https://packaging.python.org/guides/distributing-packages-using-setuptools/#uploading-your-project-to-pypi
#    twine upload dist/*
