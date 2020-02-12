#!/usr/bin/env python
"""Create, delete, or change a group of Google Compute Engine VMs with names
like "{prefix}-0", "{prefix}-1", "{prefix}-2", ...

# Example: Create worker VMs grace-wcm-0, grace-wcm-1, grace-wcm-2 with metadata
# db=analysis so those workers will use the named database.
    gce grace-wcm -c3 -m db=analysis

# Example: Delete those 3 worker VMs.
    gce --delete grace-wcm -c3 -d

# Example: Set their metadata field `quit` to `when-idle`, asking Fireworkers to
# shut down when idle.
    gce grace-wcm -c3 --set -m quit=when-idle
"""

from __future__ import absolute_import, division, print_function

import argparse
import logging
import os
from pprint import pformat
import re
import sys

if os.name == 'posix' and sys.version_info[0] < 3:
    import subprocess32 as subprocess
else:
    import subprocess

from typing import Any, Dict, List, Optional
from borealis.util import gcp

#: Access Scopes for the created GCE VMs.
SCOPES = ','.join([
    'compute-rw',           # for the instance to delete itself when done
    'logging-write',        # to write StackDriver logs
    'storage-rw',           # to read/write GCS files
    'monitoring-write',     # to emit data for load monitoring
    'service-control',      # ?
    'service-management',   # ?
    'trace',                # for debugging
])


def _clean(token):
    # type: (Any) -> str
    """Clean the token of "=" and "," chars so it won't mess up a
    "key=val,key=val" metadata string.
    """
    return re.sub(r'[=,]+', '', str(token))


def _join_metadata(metadata):
    # type: (Dict[str, Any]) -> str
    """Join the metadata dictionary into a suitable shell token string."""
    return ','.join(
        '{}={}'.format(_clean(k), _clean(v)) for k, v in metadata.items())


def _options_list(options):
    # type: (dict) -> List[str]
    """Translate a dict into a list of CLI "--option=value" tokens."""
    # E.g. ["--description=fire worker", "--metadata=k1=v1,k2=v2", "--quiet"]
    return ['--{}{}'.format(_clean(k), '' if v is None else '={}'.format(v))
            for k, v in options.items()]


class ComputeEngine(object):
    """Runs `gcloud compute` to create, delete, or change a group of GCE VM
    instances named "{prefix}-{index}".
    """

    MAX_VMS = 100  # don't create more than this many GCE VMs at a time

    def __init__(self, name_prefix, dry_run=False, verbose=False):
        # type: (str, bool, bool) -> None
        assert name_prefix, 'the name_prefix must not be empty'

        self.name_prefix = name_prefix
        self.dry_run = dry_run
        self.verbose = verbose

    def make_names(self, base=0, count=1):
        # type: (int, int) -> List[str]
        """Return a list of GCE VM names in the form "{prefix}-{index}" over the
        range [base .. count], sanitizing the name prefix to a legal VM name
        string and eliding "workflow" for brevity.
        """
        sanitized = re.sub(
            r'[^-a-z0-9]+', '-',
            self.name_prefix.lower().replace('workflow', ''))
        names = ['{}-{}'.format(sanitized, i) for i in range(base, base + count)]
        return names

    def _log_header(self, action, instance_names):
        # type: (str, List[str]) -> None
        dry = 'Dry run for: ' if self.dry_run else ''
        count = len(instance_names)
        vms = ('VMs' if count == 0
               else 'VM: {}'.format(instance_names[0]) if count == 1
               else 'VMs: {} .. {}'.format(instance_names[0], instance_names[-1]))
        logging.info('%s%s %s Google Compute Engine %s', dry, action, count, vms)

    def create(self, base=0, count=1, command_options=None, **metadata):
        # type: (int, int, Optional[Dict[str, Any]], **Any) -> None
        """In parallel, create a group of GCE VM instances.

        This provides default command options to `gcloud compute instances create`.
        The caller should at least set the `image-family` option and override
        default options as needed.

        This converts `command_options` and `metadata` to strings, stripping any
        ',' and '=' characters from the metadata fields, then passes tokens to
        `gcloud` without shell quoting risks.

        If `dry_run`, this logs the constructed `gcloud` command instead of
        running it, or if `verbose`, this logs the `gcloud` command before
        running it.
        """
        assert 0 <= count <= self.MAX_VMS, 'create-instance count ({}) must be in the range [0 .. {}]'.format(
            count, self.MAX_VMS)
        instance_names = self.make_names(base, count)

        self._log_header('Creating', instance_names)
        if count <= 0:
            return

        project = gcp.project()
        options = {
            'project': project,
            'image-project': project,
            'zone': gcp.zone(),
            'machine-type': 'n1-standard-1',
            'subnet': 'default',
            'network-tier': 'PREMIUM',
            'maintenance-policy': 'MIGRATE',
            'boot-disk-type': 'pd-standard',
            'scopes': SCOPES,
        }
        options.update(command_options or {})

        metadata_string = _join_metadata(metadata)
        if metadata_string:
            options['metadata'] = metadata_string

        options_list = _options_list(options)
        cmd_tokens = ['gcloud', 'compute', 'instances', 'create'
            ] + instance_names + options_list

        if self.dry_run or self.verbose:
            logging.info('%s', pformat(cmd_tokens))

        if not self.dry_run:
            subprocess.call(cmd_tokens)

    def delete(self, base=0, count=1, command_options=None):
        # type: (int, int, Optional[Dict[str, Any]]) -> None
        """In parallel, delete a group of GCE VM instances.

        If `dry_run`, this logs the constructed `gcloud` command instead of
        running it, or if `verbose`, this logs the `gcloud` command before
        running it.

        If command_options includes {'quiet': None}, gcloud won't ask for
        confirmation to irreversibly auto-delete disks.
        """
        instance_names = self.make_names(base, count)

        self._log_header('Deleting', instance_names)
        if count <= 0:
            return

        project = gcp.project()
        options = {
            'project': project,
            'zone': gcp.zone()}
        options.update(command_options or {})

        options_list = _options_list(options)
        cmd_tokens = ['gcloud', 'compute', 'instances', 'delete'
            ] + instance_names + options_list

        if self.dry_run or self.verbose:
            logging.info('%s', pformat(cmd_tokens))

        if not self.dry_run:
            subprocess.call(cmd_tokens)

    def set_metadata(self, base=0, count=1, command_options=None, **metadata):
        # type: (int, int, Optional[Dict[str, Any]], **Any) -> None
        """Set metadata fields on a group of GCE VM instances.

        If `dry_run`, this logs the constructed `gcloud` command instead of
        running it, or if `verbose`, this logs the `gcloud` command before
        running it.

        NOTE: This supports 'key=value' and 'key=' but doesn't yet support a
        plain 'key' which is the way to remove a key/value field.
        """
        instance_names = self.make_names(base, count)

        self._log_header('Setting metadata on', instance_names)
        if count <= 0:
            return

        project = gcp.project()
        metadata_string = _join_metadata(metadata)
        options = {
            'project': project,
            'zone': gcp.zone(),
            'metadata': metadata_string}
        options.update(command_options or {})

        options_list = _options_list(options)
        for name in instance_names:
            cmd_tokens = ['gcloud', 'compute', 'instances', 'add-metadata', name
                ] + options_list

            if self.dry_run or self.verbose:
                logging.info('%s', pformat(cmd_tokens))

            if not self.dry_run:
                subprocess.call(cmd_tokens)


def cli():
    parser = argparse.ArgumentParser(
        description='''Create, delete, or set metadata on a group of Google
            Compute Engine VMs, e.g. workflow workers that start up from a disk
            image. (This code also has an API for direct use.)''')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--delete', action='store_const', dest='action',
        const='delete', default='create',
        help='Delete VMs instead of creating VMs.')
    group.add_argument('--set-metadata', action='store_const', dest='action',
        const='metadata',
        help='Set metadata on VMs instead of creating VMs. Set `-m quit=when-idle`'
             ' to ask the specified Fireworkers to shut down gracefully.')

    parser.add_argument('name_prefix', metavar='NAME-PREFIX',
        help='The GCE VM name prefix for constructing a batch of VM names of the'
             ' form {PREFIX}-{NUMBER}.')
    parser.add_argument('-d', '--dry-run', action='store_true', dest='dry_run',
        help='Dry run: Print the constructed gcloud commands and exit.')
    parser.add_argument('-b', '--base', type=int, default=0,
        help='The base number for the VM name suffixes (default=0). This is'
             ' mainly for creating additional VMs since they need unique names.')
    parser.add_argument('-c', '--count', type=int, default=1,
        help='The number of VMs to create/delete/set (default=1).')
    parser.add_argument('-f', '--family', default='fireworker',
        help='The GCE Disk Image Family to create from (default="fireworker").'
             ' ("sisyphus-worker" is also interesting.) (With "fireworker", be'
             ' sure to set `-m db=MY_DATABASE_NAME`. With "sisyphus-worker", be'
             ' sure to set `-m workflow=MY_WORKFLOW_NAME`.)')
    parser.add_argument('-s', '--service-account', dest='service_account',
        help='The service account identity to attach when creating VMs, e.g.'
             ' "999999999999-compute@developer.gserviceaccount.com".')
    parser.add_argument('-m', '--metadata', metavar='KEY=VALUE',
        action='append', default=[],
        help='A custom GCE metadata "key=value" setting, e.g. "db=analyze" to'
             ' point FireWorks workers to a LaunchPad database. (You can use'
             ' this option zero or more times.)')

    args = parser.parse_args()
    unpacked = [e.split('=', 2) + [''] for e in args.metadata]
    metadata = {e[0]: e[1] for e in unpacked}

    # Cross-check the args.
    if args.action == 'create':
        if args.family == 'sisyphus-worker':
            assert metadata.get('workflow'), (
                'need `-m workflow=MY_WORKFLOW_NAME` to create sisyphus workers')
        if args.family == 'fireworker':
            assert metadata.get('db'), (
                'need `-m db=MY_DATABASE_NAME` to create Fireworkers')
    elif args.action == 'metadata':
        assert metadata, 'need some metadata to set'

    compute_engine = ComputeEngine(args.name_prefix, dry_run=args.dry_run)

    if args.action == 'create':
        options = {
            'image-family': args.family,
            'description': args.family + ' worker'}
        if args.service_account:
            options['service-account'] = args.service_account
        compute_engine.create(args.base, args.count, command_options=options,
                              **metadata)
    elif args.action == 'delete':
        compute_engine.delete(args.base, args.count)
    elif args.action == 'metadata':
        compute_engine.set_metadata(args.base, args.count, **metadata)


if __name__ == '__main__':
    cli()
