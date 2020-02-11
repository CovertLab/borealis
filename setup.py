from setuptools import setup

with open('README.md', 'r') as fh:
    long_description = fh.read()

setup(
    name='borealis-fireworks',
    version='0.1.0',
    packages=['borealis', 'borealis.util'],
    url='https://github.com/CovertLab/borealis',
    license='MIT',
    author='Jerry Morrison',
    author_email='j.erry.morrison@gmail.com',
    description='Run FireWorks workflows in Google Cloud',
    long_description=long_description,
    long_description_content_type='text/markdown',
    install_requires=[
        'google-cloud-logging>=1.14.0',
        'google-cloud-storage>=1.25.0',
        'docker>=4.1.0',
        'FireWorks>=1.9.5',
        'requests>=2.22.0',
        'ruamel.yaml>=0.16.7',
        'subprocess32>=3.5.4',
    ],
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
    ],
    keywords='fireworks workflow',
)
