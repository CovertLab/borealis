#!/usr/bin/env python
"""Create, delete, or change a group of Google Compute Engine VMs with names
like "{prefix}-0", "{prefix}-1", "{prefix}-2", ...

# Example: Create worker VMs grace-wcm-0, grace-wcm-1, grace-wcm-2 with metadata
# db=analysis so those workers will use the database named "analysis".
    gce grace-wcm -c3 -m db=analysis

# Example: A dry run of that command to see all the options and metadata fields.
    gce grace-wcm -c3 -m db=analysis -d

# Example: Delete those 3 worker VMs.
    gce --delete grace-wcm -c3

# Example: Set their metadata field `quit` to `soon`, asking Fireworkers to shut
# down soon (between rockets).
    gce grace-wcm -c3 --set -m quit=soon
"""

import argparse
from pprint import pprint
import re
import subprocess

from borealis.util import data
from borealis.util import gcp
import ruamel.yaml as yaml
from typing import Any, Dict, List, Optional

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

#: Default options for creating GCE VM instances.
# Don't put 'subnet': 'default' here since that'd interfere with the
# `-o network-interface=no-address` option that creates VMs without
# External IP addresses.
#
# The underlying API currently defaults to:
#   machine-type=n1-standard-1
#   boot-disk-type=pd-standard
#   ephemeral external network-interface
DEFAULT_INSTANCE_OPTIONS = {
    'machine-type': 'n1-standard-1',  # n1-standard-1 has 1 vCPU, 3.75 GB RAM
    'network-tier': 'PREMIUM',
    'maintenance-policy': 'MIGRATE',
    'boot-disk-type': 'pd-standard',
    'scopes': SCOPES,
}

DEFAULT_LPAD_YAML = 'my_launchpad.yaml'


def _clean_key(key):
    # type: (Any) -> str
    """Clean the key so it won't mess up a "key=k=v" string."""
    return str(key).replace('=', '_')


def _join_metadata(metadata):
    # type: (Dict[str, Any]) -> str
    """Join the metadata dictionary into a shell argument string. Use a custom
    delimiter ||| (see `gcloud topic escaping`) so values can contain ','.
    TODO: Check if the keys and values contain the ||| delimiter.
    """
    return '^|||^' + '|||'.join(
        '{}={}'.format(_clean_key(k), v)
        for k, v in metadata.items() if v is not None)


def _options_list(options):
    # type: (dict) -> List[str]
    """Translate a dict into a list of CLI "--option=value" tokens."""
    # E.g. ["--description=fire worker", "--metadata=k1=v1,k2=v2", "--quiet"]
    return ['--{}{}'.format(_clean_key(k), '' if v is None else '={}'.format(v))
            for k, v in options.items()]


def _parse_options(options_list: Optional[List[str]]) -> Dict[str, str]:
    """Parse the KEY=VALUE or KEY=k=v option strings into a dict."""
    assignments = options_list or []
    pairs = [a.split('=', 1) + [''] for a in assignments]  # [''] to handle the no-'=' case
    options = {p[0].strip(): p[1].strip() for p in pairs if p[0].strip()}
    return options


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
        print('{}{} {} Google Compute Engine {}'.format(dry, action, count, vms))

    def create(self, base=0, count=1, command_options=None, **metadata):
        # type: (int, int, Optional[Dict[str, Any]], **Any) -> None
        """In parallel, create a group of GCE VM instances.

        This provides default command options to `gcloud compute instances create`.
        The caller should at least set the `image-family` option.

        This converts `command_options` and `metadata` to strings, stripping any
        ',' and '=' characters from the metadata fields, then passes tokens to
        `gcloud` without shell quoting risks.

        If `dry_run`, this logs the constructed `gcloud` command instead of
        running it, or if `verbose`, this logs the `gcloud` command before
        running it.

        To allocate a larger VM pass in a different machine-type option such as:
        command_options={'machine-type'='custom-1-5120'}, or
        command_options={'machine-type'='n2-standard-2'}.
        """
        assert 0 <= count, f'negative GCE create-instance count ({count})'
        if count > self.MAX_VMS:
            print(f'WARNING: Limited the GCE create-instance count ({count}) to'
                  f' {self.MAX_VMS} to avoid an expensive accident. If/when you'
                  f' need more instances, run the `gce` command again.')
            count = self.MAX_VMS
        instance_names = self.make_names(base, count)

        self._log_header('Creating', instance_names)
        if count <= 0:
            return

        project = gcp.project()
        options = dict(DEFAULT_INSTANCE_OPTIONS)
        options.update({
            'project': project,
            'image-project': project,
            'zone': gcp.zone(),
        })
        options.update(command_options or {})

        metadata_string = _join_metadata(metadata)
        if metadata_string:
            options['metadata'] = metadata_string

        options_list = _options_list(options)
        cmd_tokens = ['gcloud', 'compute', 'instances', 'create'
            ] + instance_names + options_list

        if self.dry_run or self.verbose:
            pprint(cmd_tokens)

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
            pprint(cmd_tokens)

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
                pprint(cmd_tokens)

            if not self.dry_run:
                subprocess.call(cmd_tokens)


def cli():
    parser = argparse.ArgumentParser(
        description='''Create, delete, or set metadata on a group of Google
            Compute Engine VMs, e.g. workflow workers that start up from a disk
            image-family. (This code also has an API for direct use.)''')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--delete', action='store_const', dest='action',
        const='delete', default='create',
        help='Delete VMs instead of creating VMs.')
    group.add_argument('--set-metadata', action='store_const', dest='action',
        const='metadata',
        help='Set metadata on existing VMs instead of creating VMs. E.g. use'
             ' with `-m quit=soon` or `-m quit=when-idle`'
             ' to ask the specified Fireworkers to shut down gracefully.')
    group.add_argument('--quit-soon', action='store_const', dest='action',
        const='quit-soon',
        help='Shorthand for `--set-metadata -m quit=soon`. Asks VMs to quit'
             ' soon, assuming they check this metadata field.')

    parser.add_argument('name_prefix', metavar='NAME-PREFIX',
        help='The GCE VM name prefix for constructing a batch of VM names of the'
             ' form {NAME-PREFIX}-{NUMBER}.')
    parser.add_argument('-d', '--dry-run', action='store_true', dest='dry_run',
        help='Dry run: Print the constructed gcloud command and exit.')
    parser.add_argument('-b', '--base', type=int, default=0,
        help='The base NUMBER for the VM name suffixes (default=0). This lets'
             ' you create additional VMs with unique names.')
    parser.add_argument('-c', '--count', type=int, default=1,
        help='The number of VMs to create/delete/set (default=1).')
    parser.add_argument('-f', '--family', default='fireworker',
        help='The GCE Disk image-family to create VMs from (default="fireworker").'
             ' (For "fireworker", be sure to also set the `db` metadata field'
             ' or read a LaunchPad file that has a `name` field.)')
    parser.add_argument('-l', dest='launchpad_filename',
        default=DEFAULT_LPAD_YAML,
        help='LaunchPad config YAML filename to read the db name, username,'
             ' and password metadata when creating VMs (default="{}"). This'
             ' will create GCE VMs which connect to that LaunchPad db.'
             ' Use `-l ""` to skip this config file.'.format(DEFAULT_LPAD_YAML))
    parser.add_argument('-m', '--metadata', metavar='METADATA_KEY=VALUE',
        action='append',
        help='A GCE metadata "KEY=VALUE" setting for creating VMs'
             ' or setting their metadata, e.g. "db=analyze" to point FireWorks'
             ' workers to the database named `analyze`. Repeat as needed. These'
             ' settings override'
             ' fields read from a LaunchPad config file.')
    parser.add_argument('-o', '--option', metavar='OPTION_KEY=VALUE',
        action='append',
        help='A "KEY=VALUE" option to pass to'
             ' `gcloud compute instances create`, e.g. "boot-disk-size",'
             ' "custom-cpu", "custom-memory", "machine-type", "scopes",'
             ' "service-account". Repeat as needed. These options override'
             ' defaults and the --family argument.'
             ' Options like `project` default to'
             ' your current gcloud configuration.'
             ' Use "network-interface=no-address" to create VMs without'
             ' External IP addresses. That makes them more secure but'
             ' you\'ll need to set up Cloud NAT (so they can access Docker'
             ' repositories, PyPI, ...) and Identity-Aware Proxy (IAP)'
             ' (so you can ssh in).')

    args = parser.parse_args()
    metadata = {}

    if args.launchpad_filename and args.action == 'create':
        with open(args.launchpad_filename) as f:
            yml = yaml.YAML(typ='safe')
            lpad_config = yml.load(f)  # type: dict
            lpad_config['db'] = lpad_config.get('name')
        metadata = data.select_keys(lpad_config, ('db', 'username', 'password'))

    metadata.update(_parse_options(args.metadata))
    options = {}
    if args.action == 'create':
        if args.family:
            options['image-family'] = args.family
            options['description'] = args.family + ' worker'
        options.update(_parse_options(args.option))

    if args.action == 'quit-soon':
        args.action = 'metadata'
        metadata['quit'] = 'soon'

    # Cross-check the args.
    if args.action == 'create':
        assert options.get('image-family'), (
            'need an image-family option to create workers')
        if args.family == 'fireworker':
            assert metadata.get('db'), (
                'need a `db` metadata setting to create Fireworkers')
    elif args.action == 'metadata':
        assert metadata, 'need some metadata to set'

    compute_engine = ComputeEngine(args.name_prefix, dry_run=args.dry_run)

    if args.action == 'create':
        compute_engine.create(args.base, args.count, command_options=options,
                              **metadata)
    elif args.action == 'delete':
        compute_engine.delete(args.base, args.count)
    elif args.action == 'metadata':
        compute_engine.set_metadata(args.base, args.count, **metadata)


if __name__ == '__main__':
    cli()
