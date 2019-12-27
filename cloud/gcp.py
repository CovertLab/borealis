"""Google Cloud Platform utilities."""

from __future__ import absolute_import, division, print_function

import requests
import sys
from typing import Optional

from util import filepath as fp


def gcloud_get_config(section_property):
    # type: (str) -> str
    """Get a "section/property" configuration property from the gcloud command
    line tool. Raises an exception if the value is not configured.
    """
    return fp.run_cmd(['gcloud', 'config', 'get-value', str(section_property)])


def gcp_project():
    # type: () -> str
    """Get the current Google Cloud Platform (GCP) project."""
    return gcloud_get_config('core/project')


def gce_zone():
    # type: () -> str
    """Get the current Google Compute Engine (GCE) zone."""
    return gce_instance_metadata('zone') or gcloud_get_config('compute/zone')


def gce_instance_metadata(field, default=None):
    # type: (str, str) -> Optional[str]
    """Get a Google Compute Engine VM instance metadata field like the "name",
    "zone", or "attributes/db" for a metadata field "db". On failure (e.g.
    ConnectionError when not running on GCE) print a message and return `default`.

    "attributes/*" metadata fields can be set when creating an instance:
    `gcloud compute instances create worker --metadata db=fred ...`

    and set or changed on a running instance:
    `gcloud compute instances add-metadata instance-name --metadata db=ginger`
    """
    url = "http://metadata.google.internal/computeMetadata/v1/instance/{}".format(field)
    headers = {'Metadata-Flavor': 'Google'}
    timeout = 5  # seconds

    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        return r.text if r.status_code == 200 else default
    except requests.exceptions.RequestException as e:
        print('Note: Couldn\'t connect to GCP Metadata server to get "{}".'
            .format(field))
        return default


def gce_instance_name():
    # type: () -> str
    """Return this GCE VM instance name, or None if not running on GCE."""
    return gce_instance_metadata('name')


def delete_this_vm():
    # type: () -> None
    """Ask gcloud to delete this GCE VM instance (if running on GCE), then exit
    (if not already shut down) maybe allowing cleanup actions to run.
    """
    name = gce_instance_name()
    if name:
        print('GCE VM "{}" shutting down...'.format(name))
        fp.run_cmd(['gcloud', 'compute', 'instances', 'delete', name])
    else:
        print('Exiting (not running on GCE).')
    sys.exit()
