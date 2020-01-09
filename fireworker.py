#!/usr/bin/env python
"""A Fireworks worker on Google Compute Engine to "rapidfire" launch rockets."""

# TODO(jerry): Investigate Live Migration, Maintenance events, preemptible
# instances, availability policies, restart behavior,

from __future__ import absolute_import, division, print_function

import argparse
import os
import socket
import time
import traceback

from fireworks import LaunchPad, FWorker
from fireworks.core import rocket_launcher
from fireworks.utilities import fw_utilities
import ruamel.yaml as yaml
from typing import Any, Dict

from cloud import gcp
from util import filepath as fp


# The standard launchpad config file. We'll read it and override some fields.
LAUNCHPAD_FILE = 'my_launchpad.yaml'

# Default directory for FireWorks logs.
DEFAULT_LOGDIR = os.path.join(os.environ.get('HOME', os.getcwd()), 'logs', 'worker')


# TODO(jerry): a Firetask that pulls inputs from & pushes outputs to GCS, runs
# the target in a Docker container, and uses StackDriver logging. Do StackDriver
# here, too?


class Fireworker(object):

    def __init__(self, lpad_config, instance_name):
        # type: (Dict[str, Any], str) -> None
        self.lpad_config = lpad_config
        self.strm_lvl = lpad_config.get('strm_lvl') or 'INFO'
        self.instance_name = instance_name

        self.sleep_secs = 10
        self.idle_for_waiters = 60 * 60
        self.idle_for_queued = 15 * 60

        self.launchpad = LaunchPad(**lpad_config)

        # TODO(jerry): Adopt StackDriver logging here? Redirect FireWorks logging?
        self.logger = fw_utilities.get_fw_logger(
            'fireworker',
            l_dir=self.launchpad.get_logdir(),
            stream_level=self.strm_lvl)

        # Could optionally set a specific `category` of jobs to pull, a `query`
        # to restrict the type of Fireworks to run, and an `env` to pass
        # worker-specific into to the Firetasks.
        self.fireworker = FWorker(instance_name)

    def launch_rockets(self):
        # type: () -> None
        """Launch rockets, logging exceptions."""
        try:
            self._launch_rockets()
        except KeyboardInterrupt as e:
            fw_utilities.log_multi(self.logger, repr(e), 'error')
        except Exception:
            fw_utilities.log_exception(self.logger, 'fireworker exception')

    def _launch_rockets(self):
        # type: () -> None
        """Keep launching rockets that are ready to go, idling up to
        idle_for_waiters for waiting rockets to become ready or idle_for_queued
        if none are even waiting, or until the custom metadata field
        attributes/quit becomes 'when-idle'.

        There are two timeouts so idle workers give running rockets time to
        finish work needed for queued dependent rockets and otherwise (when
        nothing is queued up) allow some time for new work to get queued.
        """

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
                self.launchpad, self.fireworker, strm_lvl=self.strm_lvl,
                max_loops=1, sleep_time=self.sleep_secs)

            # Idle to the max.
            idled = self.sleep_secs  # rapidfire() just slept once
            while not self.launchpad.run_exists(self.fireworker):  # none ready to run
                future_work = self.launchpad.future_run_exists(self.fireworker)  # any waiting?
                if idled >= (self.idle_for_waiters if future_work else self.idle_for_queued):
                    return

                if gcp.instance_metadata(
                        'attributes/quit', '', complain_off_gcp=False) == 'when-idle':
                    fw_utilities.log_multi(self.logger, 'Requested to quit when-idle')
                    return

                fw_utilities.log_multi(
                    self.logger,
                    'Sleeping for {} secs waiting for rockets to launch'.format(self.sleep_secs))
                time.sleep(self.sleep_secs)
                idled += self.sleep_secs


def main(development=False):
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

    TODO: Add configuration settings for idle_for_waiters and idle_for_queued.

    You can set a custom metadata field to make this worker stop idling:
        gcloud compute instances add-metadata INSTANCE-NAME --metadata quit=when-idle
    """
    with open(LAUNCHPAD_FILE) as f:
        lpad_config = yaml.safe_load(f)  # type: dict

    instance_name = gcp.gce_instance_name() or socket.gethostname()
    db_name = (gcp.instance_metadata('attributes/db')
               or lpad_config.get('name', 'default_fireworks_database'))
    lpad_config['name'] = db_name

    username = (gcp.instance_metadata('attributes/username')
                or lpad_config.get('username'))
    password = (gcp.instance_metadata('attributes/password')
                or lpad_config.get('password'))
    lpad_config['username'] = username
    lpad_config['password'] = password

    logdir = lpad_config.setdefault('logdir', DEFAULT_LOGDIR)
    if logdir:
        fp.makedirs(logdir)

    print('\nStarting fireworker on {} with LaunchPad config: {}\n'.format(
        instance_name, lpad_config))

    try:
        fireworker = Fireworker(lpad_config, instance_name)
        fireworker.launch_rockets()
    except Exception:
        print('\nfireworker error: {}'.format(traceback.format_exc()))

    if not development:
        gcp.delete_this_vm()


def cli():
    parser = argparse.ArgumentParser(
        description='Run as a FireWorks worker node, launching rockets rapidfire.'
                    ' Designed for Google Compute Engine (GCE).'
                    ' Gets configuration settings from GCE and my_launchpad.yaml,'
                    ' with fallbacks.')
    parser.add_argument(
        '--development', action='store_true',
        help="Development mode: When done, just exit Python without deleting"
             " this GCE VM worker instance (moot when running off GCE).")

    args = parser.parse_args()
    main(development=args.development)


if __name__ == '__main__':
    cli()
