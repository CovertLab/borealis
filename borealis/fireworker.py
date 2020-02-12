#!/usr/bin/env python
"""A Fireworks worker on Google Compute Engine to "rapidfire" launch rockets.

    python -m borealis.fireworker

The borealis-fireworker installs a console_scripts for fireworker and gce, so
you can simply run

    fireworker

NOTE: When running as a systemd service or otherwise outside an interactive
console, set the `PYTHONUNBUFFERED=1` environment variable or run with
`python -u fireworker.py` so the logging output comes out in real time rather
than buffering up into long delayed chunks.
"""

from __future__ import absolute_import, division, print_function

import argparse
import logging
import socket
import sys
import time
from typing import Any, Dict

from fireworks import LaunchPad, FWorker, fw_config
from fireworks.core import rocket_launcher
import google.cloud.logging as gcl
from google.cloud.logging.resource import Resource
import ruamel.yaml as yaml

# import logging_tree

from borealis.util import gcp
from borealis.util.log_filter import LogPrefixFilter

#: The standard launchpad config filename (in CWD) to read.
#: GCE instance metadata will override some field values.
LAUNCHPAD_FILE = 'my_launchpad.yaml'
DEFAULT_FIREWORKS_DATABASE = 'default_fireworks_database'

ERROR_EXIT_CODE = 1
KEYBOARD_INTERRUPT_EXIT_CODE = 2

#: Fireworker logger.
FW_LOGGER = logging.getLogger('fireworker')
FW_LOGGER.setLevel(logging.DEBUG)

#: Fireworker console-only logger.
FW_CONSOLE_LOGGER = logging.getLogger('fireworker.console')
FW_CONSOLE_LOGGER.setLevel(logging.DEBUG)
FW_CONSOLE_LOGGER.propagate = False


def _setup_logging(gce_instance_name, host_name):
    # type: (str, str) -> None
    """Set up GCP StackDriver cloud logging on Python's root logger for the GCE
    instance name or any host name. Set a narrow logging filter if running off
    GCE (instance_name is empty).
    """
    exclude = (FW_CONSOLE_LOGGER.name, 'urllib3')

    monitored_resource = Resource(
        type='gce_instance',
        labels={  # Add a 'tag' label? It gets 'project_id' automatically.
            'instance_id': host_name,
            'zone': gcp.zone()})
    client = gcl.Client()

    # noinspection PyTypeChecker
    client.setup_logging(
        log_level=logging.WARNING,
        excluded_loggers=exclude,
        name=FW_LOGGER.name,
        resource=monitored_resource)

    # For aggregate cloud logs: Filter out debug details and when running off
    # GCE also filter out the dockerfiretask payload stdout lines, keeping just
    # the WARNINGs and start/end messages. (Use WARNING rather than NOTICE level
    # for start/end because Logs Viewer doesn't support NOTICE very well.) We
    # can't `exclude` those loggers since that'd block their WARNINGs.
    #
    # Console logs: Filter out messages already printed by handlers of nested
    # loggers "launchpad" and "rocket.launcher", allowing WARNINGs just in case.
    root = logging.getLogger()
    fworker_level = logging.DEBUG if gce_instance_name else logging.WARNING
    cloud_filter = LogPrefixFilter(
        {'fireworker': fworker_level, 'dockerfiretask': fworker_level},
        logging.WARNING)
    console_filter = LogPrefixFilter(
        {'fireworker': logging.INFO, 'dockerfiretask': logging.DEBUG},
        logging.WARNING)
    for handler in root.handlers:
        # This `is_cloud` test is a bit fragile.
        is_cloud = hasattr(handler, 'transport') or hasattr(handler, 'resource')
        handler.addFilter(cloud_filter if is_cloud else console_filter)


def _cleanup_logging():
    # type: () -> None
    """Clean up StackDriver cloud logging: Flush and remove root logger's
    background-transport handlers so the last messages get to the server and
    won't raise RuntimeError('cannot schedule new futures after shutdown').

    StackDriver should be out of the loop after this but there's no documented
    API for this so hopefully it's right, idempotent, and safe if StackDriver
    logging was not set up.
    """
    root = logging.getLogger()

    for handler in root.handlers.copy():
        if hasattr(handler, 'transport'):
            transport = handler.transport
            if hasattr(transport, 'flush'):
                transport.flush()
                root.removeHandler(handler)


class Fireworker(object):
    """A Fireworks worker on Google Compute Engine to "rapidfire" launch rockets.

    NOTE: When running as a systemd service or otherwise outside an interactive
    console, set the `PYTHONUNBUFFERED=1` environment variable or run with
    `python -u fireworker.py` so the logging output comes out in real time rather
    than buffering up into long delayed chunks.
    """

    def __init__(self, lpad_config, host_name):
        # type: (Dict[str, Any], str) -> None
        self.lpad_config = lpad_config
        self.host_name = host_name

        # NOTE: FireWorks creates loggers with stdout stream handlers for each
        # (name, level) pair. So setting strm_lvl='WARNING' gets both INFO and
        # WARNING handlers which might print duplicate lines. Try to tame it.
        self.strm_lvl = lpad_config.get('strm_lvl') or 'INFO'
        fw_config.ROCKET_STREAM_LOGLEVEL = self.strm_lvl

        self.sleep_secs = 10
        self.idle_for_waiters = 60 * 60
        self.idle_for_queued = 15 * 60  # TODO(jerry): Rename this

        self.launchpad = LaunchPad(**lpad_config)
        self.launchpad.m_logger.setLevel(self.strm_lvl)  # set non-stream level

        # Can optionally set a specific `category` of jobs to pull, a `query`
        # to restrict the type of Fireworks to run, and an `env` to pass
        # worker-specific into to the Firetasks.
        self.fireworker = FWorker(host_name)

    def launch_rockets(self):
        # type: () -> None
        """Keep launching rockets that are ready to go. Stop after:
          * idling idle_for_waiters secs for WAITING rockets to become ready,
          * idling idle_for_queued secs if no rockets are even waiting,
          * the custom metadata field `attributes/quit` becomes 'when-idle'.

        The first timeout should be long enough to wait around to run queued
        rockets after running rockets finish prerequisite work. The second
        timeout should be long enough to let new work get queued.
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

            # logging_tree.printout()  # *** DEBUG ***

            # Idle to the max.
            idled = self.sleep_secs  # rapidfire() just slept once
            while not self.launchpad.run_exists(self.fireworker):  # none ready to run
                future_work = self.launchpad.future_run_exists(self.fireworker)  # any waiting?
                if idled >= (self.idle_for_waiters if future_work else self.idle_for_queued):
                    return

                if gcp.instance_metadata('attributes/quit') == 'when-idle':
                    FW_LOGGER.info('Quitting by "when-idle" request')
                    return

                FW_CONSOLE_LOGGER.info(
                    'Sleeping for %s secs waiting for launchable rockets',
                    self.sleep_secs)
                time.sleep(self.sleep_secs)
                idled += self.sleep_secs


class Redacted(object):
    def __repr__(self):
        """Print without quotes to look like a mask not a lame password."""
        return '*****'


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
        logdir, strm_lvl, ... [optional, for "launchpad" & "rocket" logging]
        DB name, DB username, and DB password [fallback]
    with fallbacks:
        name - 'fireworker'
        DB name - DEFAULT_FIREWORKS_DATABASE
        DB username, DB password - null
        logdir, strm_lvl - FireWorks defaults

    The DB username and password are needed if MongoDB is set up to require
    authentication, and it could use shared or user-specific accounts.

    TODO: Add configuration settings for idle_for_waiters and idle_for_queued.

    You can set a custom metadata field to make this worker stop idling:
        gcloud compute instances add-metadata INSTANCE-NAME --metadata quit=when-idle
    """
    exit_code = ERROR_EXIT_CODE

    try:
        instance_name = gcp.gce_instance_name()
        host_name = instance_name or socket.gethostname()
        _setup_logging(instance_name, host_name)

        with open(LAUNCHPAD_FILE) as f:
            lpad_config = yaml.safe_load(f)  # type: dict

        db_name = (gcp.instance_metadata('attributes/db')
                   or lpad_config.get('name', DEFAULT_FIREWORKS_DATABASE))
        lpad_config['name'] = db_name

        username = (gcp.instance_metadata('attributes/username')
                    or lpad_config.get('username'))
        password = (gcp.instance_metadata('attributes/password')
                    or lpad_config.get('password'))
        lpad_config['username'] = username
        lpad_config['password'] = password

        redacted_config = dict(lpad_config, password=Redacted())
        FW_LOGGER.warning(
            '\nStarting Fireworker on %s with LaunchPad config: %s\n',
            host_name, redacted_config)

        fireworker = Fireworker(lpad_config, host_name)
        fireworker.launch_rockets()

        FW_LOGGER.warning("Fireworker -- normal exit")
        exit_code = 0
    except KeyboardInterrupt:
        FW_LOGGER.warning('Fireworker -- KeyboardInterrupt exit')
        exit_code = KEYBOARD_INTERRUPT_EXIT_CODE
    except Exception:
        FW_LOGGER.exception('Fireworker -- error exit')

    _cleanup_logging()
    _shut_down(development, exit_code)


def _shut_down(development, exit_code):
    # type: (bool, int) -> None
    """Shut down this program or this entire GCE VM (if running on GCE and not
    `development` and `exit_code` isn't KEYBOARD_INTERRUPT_EXIT_CODE).
    """
    if development or exit_code == KEYBOARD_INTERRUPT_EXIT_CODE:
        sys.exit(exit_code)
    else:
        if exit_code:  # an unexpected failure, e.g. missing a needed pip
            FW_CONSOLE_LOGGER.warning(
                'Delaying before deleting this GCE VM to allow some time to'
                ' connect to it and stop this service so you can fix the problem'
                ' and make a new Disk Image.')
            time.sleep(15 * 60)

        gcp.delete_this_vm(exit_code)


def cli():
    """Command Line Interpreter to run a Fireworker."""
    parser = argparse.ArgumentParser(
        description='Run as a FireWorks worker node, launching rockets rapidfire.'
                    ' Designed for Google Compute Engine (GCE).'
                    ' Gets configuration settings from GCE and my_launchpad.yaml,'
                    ' with fallbacks.')
    parser.add_argument(
        '--development', action='store_true',
        help="Development mode: When done, just exit Python without deleting"
             " this GCE VM worker instance (if running on GCE).")

    args = parser.parse_args()
    main(development=args.development)


if __name__ == '__main__':
    cli()
