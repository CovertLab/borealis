#!/usr/bin/env python
"""Create, delete, or change a group of Google Compute Engine VMs."""

from __future__ import absolute_import, division, print_function

import argparse
import os
from pprint import pprint
import re
import sys

if os.name == 'posix' and sys.version_info[0] < 3:
    import subprocess32 as subprocess
else:
    import subprocess

from typing import Any, Dict, List, Optional
from cloud import gcp


#: Access permissions to grant to created GCE VMs.
SCOPES = ('storage-rw,'
          'logging-write,'
          'monitoring-write,'
          'service-control,'
          'service-management,'
          'trace')


def _clean(token):
    # type: (Any) -> str
    """Clean the token of "=" and "," chars so it won't mess up a
    "key=val,key=val" metadata string.
    """
    return re.sub(r'[=,]+', '', str(token))


class ComputeEngine(object):
    """Runs `gcloud compute` to create, delete, or change a group of GCE VM
    instances named "{prefix}-{index}".

    TODO: Use GCE Instance Groups?
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

    def create(self, base=0, count=1, command_options=None, **metadata):
        # type: (int, int, Optional[Dict[str, Any]], **Any) -> None
        """In parallel, create a group of GCE VM instances.

        This provides default command options to `gcloud compute instances create`.
        The caller should at least set the `image-family` option and override
        default options as needed.

        This converts `command_options` and `metadata` to strings, stripping any
        ',' and '=' characters from the metadata fields, then passes tokens to
        `gcloud` without shell quoting risks.

        If `dry_run`, this prints the constructed `gcloud` command instead of
        running it, or if `verbose`, this prints the `gcloud` command before
        running it.
        """
        assert 0 <= count < self.MAX_VMS, 'instance count ({}) must be in the range [0 .. {}]'.format(
            count, self.MAX_VMS)
        instance_names = self.make_names(base, count)

        dry = 'Dry run for: ' if self.dry_run else ''
        vms = ('VMs' if count <= 0
               else 'VM: ' + instance_names[0] if count == 1
               else 'VMs: {} .. {}'.format(instance_names[0], instance_names[-1]))
        print('{}Creating {} Google Compute Engine {}'.format(dry, count, vms))
        if count <= 0:
            return

        project = gcp.project()
        options = {
            'project': project,
            'image-project': project,
            'zone': gcp.zone(complain_off_gcp=False),
            'machine-type': 'n1-standard-1',
            'subnet': 'default',
            'network-tier': 'PREMIUM',
            'maintenance-policy': 'MIGRATE',
            'boot-disk-size': '200GB',
            'boot-disk-type': 'pd-standard',
            'scopes': SCOPES}
        options.update(command_options or {})

        metadata_string = ','.join(
            '{}={}'.format(_clean(k), _clean(v)) for k, v in metadata.items())
        if metadata_string:
            options['metadata'] = metadata_string

        options_list = ['--{}={}'.format(_clean(k), v) for k, v in options.items()]
        cmd_tokens = ['gcloud', 'compute', 'instances', 'create'
            ] + instance_names + options_list

        if self.dry_run or self.verbose:
            pprint(cmd_tokens)

        if not self.dry_run:
            subprocess.call(cmd_tokens)

    # TODO(jerry): Methods to delete VMs and add-metadata.


def main():
    parser = argparse.ArgumentParser(
        description='''Create a group of Google Compute Engine VMs. If the named disk
            image family is set up as a workflow worker, they will run workflow tasks until deciding they're done. (This code also has an API for direct use.)''')
    parser.add_argument('name_prefix', metavar='NAME-PREFIX',
        help='The GCE VM name prefix for constructing VM names in the pattern'
             ' {PREFIX}-{NUMBER}.')
    parser.add_argument('-d', '--dry-run', action='store_true', dest='dry_run',
        help='Dry run: Print the constructed gcloud command and exit.')
    parser.add_argument('-b', '--base', type=int, default=0,
        help='The base number for the numbered VM names (default 0). Use this'
             ' to launch additional VMs since they need unique names.')
    parser.add_argument('-c', '--count', type=int, default=1,
        help='The number of VMs to launch (default 1).')
    parser.add_argument('-f', '--family', default='fireworker',
        help='The GCE Disk Image Family to instantiate (default "fireworker").'
             ' ("sisyphus-worker" is also interesting.) (With "fireworker", be'
             ' sure to set `-m db=MY_DATABASE_NAME`. With "sisyphus-worker", be'
             ' sure to set `-m workflow=MY_WORKFLOW_NAME`.)')
    parser.add_argument('-s', '--service-account', dest='service_account',
        help='The service account identity to attach to created GCE VMs, e.g.'
             ' "999999999999-compute@developer.gserviceaccount.com".')
    parser.add_argument('-m', '--metadata', metavar='KEY=VALUE',
        action='append', default=[],
        help='Add a custom GCE metadata "key=value" setting, e.g. "db=crick" to'
             ' point FireWorks workers to a LaunchPad database. (You can use'
             ' this option zero or more times.)')

    args = parser.parse_args()
    unpacked = [e.split('=', 2) + [''] for e in args.metadata]
    metadata = {e[0]: e[1] for e in unpacked}

    if args.family == 'sisyphus-worker':
        assert 'workflow' in metadata, (
            'need `-m workflow=MY_WORKFLOW_NAME` to launch sisyphus workers')
    elif args.family == 'fireworker':
        assert 'db' in metadata, (
            'need `-m db=MY_DATABASE_NAME` to launch fireworkers')

    options = {
        'image-family': args.family,
        'description': args.family + ' worker'}
    if args.service_account:
        options['service-account'] = args.service_account

    compute_engine = ComputeEngine(args.name_prefix, dry_run=args.dry_run)
    compute_engine.create(args.base, args.count, command_options=options, **metadata)


if __name__ == '__main__':
    main()
