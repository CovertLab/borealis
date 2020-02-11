"""Google Cloud Platform utilities."""

from __future__ import absolute_import, division, print_function

import errno
import logging
import requests
import subprocess
import sys
from typing import Optional

from borealis.util import filepath as fp

#: Console-only logger.
CONSOLE_LOGGER = logging.getLogger('fireworker.gcp')
CONSOLE_LOGGER.setLevel(logging.DEBUG)
CONSOLE_LOGGER.propagate = False


def gcloud_get_config(section_property):
    # type: (str) -> str
    """Get a "section/property" configuration value from the gcloud command line
    tool. Raise ValueError if the parameter is not set (maybe recoverable), or
    OSError if `gcloud` isn't installed or doesn't know that configuration
    parameter (which probably means the SDK needs installing or updating).
    """
    try:
        out, err = fp.run_cmd2(['gcloud', 'config', 'get-value', str(section_property)])
        if err == '(unset)':
            raise ValueError(
                'The gcloud configuration value "{0}" is unset. You can set it via'
                ' `gcloud config set {0} SOME-VALUE`'.format(section_property))
        return out

    except subprocess.CalledProcessError as e:
        if e.stderr:  # e.g. 'ERROR: (gcloud.config.get-value) Section [compute] has no property [zonE].\n'
            raise OSError(errno.EINVAL, e.stderr.rstrip())
        raise
    except OSError as e:
        raise OSError(
            e.errno,
            '{}: "{}" -- You might need to install the Google Cloud SDK and put its'
            ' `gcloud` command line program on your shell path. See {}'.format(
                e.strerror, e.filename, 'https://cloud.google.com/sdk/install'))


def project():
    # type: () -> str
    """Get the current Google Cloud Platform (GCP) project. This works both
    on and off of Google Cloud as long as the `gcloud` command line tool was
    configured.
    """
    return gcloud_get_config('core/project')


def zone():
    # type: () -> str
    """Get the current Google Compute Platform (GCP) zone from the metadata
    server when running on Google Cloud, else from the `gcloud` command line tool.
    """
    zone_metadata = instance_metadata('zone', '').split('/')[-1]
    return zone_metadata or gcloud_get_config('compute/zone')


def instance_metadata(field, default=None):
    # type: (str, str) -> Optional[str]
    """Get a metadata field like the "name", "zone", or "attributes/db" (for
    custom metadata field "db") of this Google Compute Engine VM instance from
    the GCP metadata server. If it can't contact the Metadata server (not
    running on Google Cloud) return `default`.

    "attributes/*" metadata fields can be set when creating a GCE instance:
    `gcloud compute instances create worker --metadata db=fred ...`
    They can be set or changed on a running instance:
    `gcloud compute instances add-metadata INSTANCE-NAME --metadata quit=when-idle`
    """
    url = "http://metadata.google.internal/computeMetadata/v1/instance/{}".format(field)
    headers = {'Metadata-Flavor': 'Google'}
    timeout = 5  # seconds

    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        return r.text if r.status_code == 200 else default
    except requests.exceptions.RequestException as e:
        return default


def gce_instance_name():
    # type: () -> str
    """Return this GCE VM instance name if running on GCE, or None if not
    running on GCE.
    """
    return instance_metadata('name')


def delete_this_vm(exit_code=0):
    # type: (int) -> None
    """Ask gcloud to delete this GCE VM instance if running on GCE. In any case
    exit Python if not already shut down, and Python cleanup actions might run.
    """
    name = gce_instance_name()

    if name:
        CONSOLE_LOGGER.warning('Deleting GCE VM "%s"...', name)
        my_zone = zone()
        try:
            fp.run_cmd(['gcloud', '--quiet', 'compute', 'instances', 'delete',
                        name, '--zone', my_zone])
        except subprocess.CalledProcessError as e:
            CONSOLE_LOGGER.error("Couldn't delete GCE VM %s: %s", name, e.stderr)
        except (subprocess.TimeoutExpired, OSError):
            CONSOLE_LOGGER.exception("Couldn't delete GCE VM %s", name)
    else:
        CONSOLE_LOGGER.warning('Exiting (not running on GCE).')

    sys.exit(exit_code)
