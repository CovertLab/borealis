import re
from setuptools import setup

with open('README.md', 'r') as fh:
    description = fh.read()
    # Patch the relative links so they'll work on PyPI.
    description2 = re.sub(
        r'\]\(([\w/.-]+\.png)\)',
        r'](https://github.com/CovertLab/borealis/raw/master/\1)',
        description)
    long_description = re.sub(
        r'\]\(([\w/.-]+)\)',
        r'](https://github.com/CovertLab/borealis/blob/master/\1)',
        description2)

setup(
    name='borealis-fireworks',
    version='0.6.6',
    packages=['borealis', 'borealis.util'],
    url='https://github.com/CovertLab/borealis',
    project_urls={
        'Source': 'https://github.com/CovertLab/borealis',
        'Documentation': 'https://github.com/CovertLab/borealis#borealis',
        'Changelog': 'https://github.com/CovertLab/borealis/blob/master/docs/changes.md',
    },
    license='MIT',
    author='Jerry Morrison',
    author_email='j.erry.morrison@gmail.com',
    description='Run FireWorks workflows in Google Cloud',
    long_description=long_description,
    long_description_content_type='text/markdown',
    python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*, <4',
    install_requires=[
        'google-cloud-logging>=1.14.0',
        'google-cloud-storage>=1.28.0',
        'docker>=4.1.0',
        'FireWorks>=1.9.5',
        'requests>=2.22.0',
        'ruamel.yaml>=0.16.9',
        'subprocess32>=3.5.4',
    ],
    package_data={
        'borealis': ['setup/*'],
    },
    entry_points={
        'console_scripts': [
            'fireworker=borealis.fireworker:cli',
            'gce=borealis.gce:cli',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Science/Research',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    keywords='fireworks workflow',
)
