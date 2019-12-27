#!/usr/bin/env python
"""A Fireworks worker on Google Compute Engine to "rapidfire" launch rockets."""

from __future__ import absolute_import, division, print_function

import argparse
import os
import time

from fireworks import LaunchPad, FWorker
from fireworks.core import rocket_launcher
import ruamel.yaml as yaml
from typing import Optional

from cloud import gcp
from util import filepath as fp


# The standard launchpad config file. We'll read it and override some fields.
LAUNCHPAD_FILE = 'my_launchpad.yaml'

# Default directory for FireWorks logs.
DEFAULT_LOGDIR = os.path.join(os.environ.get('HOME', os.getcwd()), 'logs', 'worker')


# TODO(jerry): a Firetask that pulls inputs from & pushes outputs to GCS, runs
# the target in a Docker container, and uses StackDriver logging. Do StackDriver
# here, too?


def launch_rockets(launchpad, fireworker, strm_lvl=None):
    # type: (LaunchPad, FWorker, Optional[str]) -> None
    """Keep launching rockets that are ready to go, idling up to 60m for waiting
    rockets to become ready or 15m if none are even waiting.
    """
    strm_lvl = strm_lvl or 'INFO'

    sleep_secs = 10
    idle_for_waiters = 60 * 60
    idle_for_queued = 15 * 60

    # rapidfire() launches READY rockets until: `max_loops` batches of READY
    # rockets OR `timeout` total elapsed seconds OR `nlaunches` rockets launched
    # OR `nlaunches` == 0 ("until completion", the default) AND no rockets are
    # even waiting.
    #
    # Set max_loops so it won't loop forever and we can track idle time.
    #
    # TODO(jerry): Set m_dir? local_redirect?
    while True:
        rocket_launcher.rapidfire(
            launchpad, fireworker, strm_lvl=strm_lvl, max_loops=1,
            sleep_time=sleep_secs)
        idle_seconds = sleep_secs  # rapidfire() just slept once

        while not launchpad.run_exists(fireworker):  # none are ready to run
            future_work = launchpad.future_run_exists(fireworker)  # any waiting?
            if idle_seconds >= (idle_for_waiters if future_work else idle_for_queued):
                return

            print('Sleeping for {} secs waiting for tasks to run'.format(sleep_secs))
            time.sleep(sleep_secs)
            idle_seconds += sleep_secs


def main(delete_this_vm=True):
    # type: (bool) -> None
    """Run as a FireWorks worker node on Google Compute Engine (GCE), launching
    Fireworks rockets in rapidfire mode then deleting this GCE VM instance.

    Get configuration settings from GCE VM metadata fields:
        name - the Fireworker name [required]
        attributes/db - DB name (user-specific or workflow-specific) [required]
        attributes/username - DB username [optional]
        attributes/password - DB password [optional]
    secondarily from my_launchpad.yaml:
        host, port - for the DB connection [required]
        logdir, strm_lvl, ... [optional]
        DB name, DB username, and DB password [fallback]
    with fallbacks:
        name - 'fireworker'
        DB name - 'default_fireworks_database'
        DB username, DB password - null
        logdir - './logs/worker' (my_launchpad takes precedence, even if null)
        strm_lvl - 'INFO'

    The DB username and password are needed if MongoDB is set up to require
    authentication, and it could use shared or user-specific accounts.

    To aid testing off GCE, ...
    """
    with open(LAUNCHPAD_FILE) as f:
        lpad_config = yaml.safe_load(f)  # type: dict

    instance_name = gcp.gce_instance_name() or 'fireworker'
    db_name = (gcp.gce_instance_metadata('attributes/db')
               or lpad_config.get('name', 'default_fireworks_database'))
    lpad_config['name'] = db_name

    username = (gcp.gce_instance_metadata('attributes/username')
                or lpad_config.get('username'))
    password = (gcp.gce_instance_metadata('attributes/password')
                or lpad_config.get('password'))
    lpad_config['username'] = username
    lpad_config['password'] = password

    logdir = lpad_config.setdefault('logdir', DEFAULT_LOGDIR)
    if logdir:
        fp.makedirs(logdir)

    print('\nFireworker config: {}\n'.format(lpad_config))

    launchpad = LaunchPad(**lpad_config)

    # Could optionally set a specific `category` of jobs to pull, a `query` to
    # restrict the type of Fireworks to run, and `env` to pass
    # configuration-specific into to the Firetasks.
    fireworker = FWorker(instance_name)

    launch_rockets(launchpad, fireworker, strm_lvl=lpad_config.get('strm_lvl'))

    if delete_this_vm:
        gcp.delete_this_vm()


def cli():
    parser = argparse.ArgumentParser(
        description='Run as a FireWorks worker node, launching rockets rapidfire.'
                    ' Designed for Google Compute Engine (GCE).'
                    ' Gets configuration settings from GCE and my_launchpad.yaml,'
                    ' with fallbacks.')
    parser.add_argument(
        '--no-delete', action='store_false', dest='delete',
        help="Don't delete this GCE VM instance when done. Useful for testing.")

    args = parser.parse_args()
    main(delete_this_vm=args.delete)


if __name__ == '__main__':
    cli()
