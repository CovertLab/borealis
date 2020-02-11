"""Interface to Google Cloud Storage (GCS)."""

from __future__ import absolute_import, division, print_function

import itertools
import logging
import os
from typing import Iterator, List, Optional, Union, Set

from google.cloud.storage import Blob, Bucket, Client
from google.cloud.exceptions import GoogleCloudError

import borealis.util.filepath as fp


OCTET_STREAM = 'application/octet-stream'


def bucket_path(pathname):
    # type: (str) -> List[str]
    """Split a GCS pathname like `my_bucket/stuff/file.txt` into bucket and path
    parts `['my_bucket', 'stuff/file.txt']`.
    """
    if pathname.startswith(os.sep):
        pathname = pathname[1:]
    parts = pathname.split(os.sep, 1)
    if len(parts) < 2:
        parts.append('')
    return parts


def names_a_directory(path):
    # type: (str) -> bool
    """Return True if the given path names a directory vs. a file (even on GCS,
    existing or yet to be created) by checking if the path ends with a '/'.
    """
    return path.endswith(os.sep)


def relpath(path, start=None):
    # type: (str, Optional[str]) -> str
    """Return a filepath relative to an optional start directory or the current
    directory -- like os.path.relpath() but keeping path's trailing '/'. This is
    just a path computation. start defaults to os.curdir.
    """
    result = os.path.relpath(path, start)
    if names_a_directory(path):
        result = os.path.join(result, '')
    return result


class CloudStorage(object):
    """A higher level interface to a GCS bucket.

    See https://cloud.google.com/storage/docs/naming about legal bucket and
    blob (aka object) names, and note that bucket names are public and must be
    globally unique.

    To run on Google Compute Engine (GCE), the VM needs access Scopes:
        Storage Read Write (storage-rw)
    and its Service Account needs Permissions:
        Storage Object Admin

    To run off GCE, configure a service account "fireworker" with the above
    permissions, get its private key as a json file:
        PROJECT="$(gcloud config get-value core/project)"
        FIREWORKER_KEY="${HOME}/bin/fireworker.json"
        gcloud iam service-accounts keys create "${FIREWORKER_KEY}" \
            --iam-account "fireworker@${PROJECT}.iam.gserviceaccount.com"
    and append an `export` statement to the shell .profile:
        echo "export GOOGLE_APPLICATION_CREDENTIALS=${FIREWORKER_KEY}" >> ~/.profile
    This will avoid a quota warning and limit.
    """

    #: For efficiency, retrieve just these Blob metadata fields.
    #: https://cloud.google.com/storage/docs/json_api/v1/how-tos/performance
    FIELDS = 'items(bucket,name,id,generation,size),nextPageToken'

    def __init__(self, storage_prefix):
        # type: (Union[Bucket, str]) -> None
        """Construct a GCS accessor with the given storage_prefix, which must
        name a GCS bucket and optionally a base path, e.g.
        'curie-workflows/sim/2020-02-02/'. (It should end with a '/' but will
        work if it doesn't.) All operations are relative to this prefix.

        Raise google.api_core.exceptions.NotFound if the bucket doesn't exist.

        File uploads to GCS will automatically create directory placeholder
        entries, which are empty objects with names ending in '/'. GCS doesn't
        require them but they make gcsfuse-mounted volumes 10x faster (gcsfuse
        without the `--implicit-dirs` option).
        """
        self.bucket_name, self.path_prefix = bucket_path(storage_prefix)
        self.path_prefix = os.path.join(self.path_prefix, '')
        if len(self.bucket_name) < 3:
            # get_bucket() checks that the bucket name is legal and the bucket
            # exists, but it trips over an empty name.
            raise ValueError("Invalid bucket name: '{}'".format(self.bucket_name))

        self.client = Client()
        self.bucket = self.client.get_bucket(self.bucket_name)

        #: A cache of directory placeholders already created or verified.
        self._directory_cache = set()  # type: Set[str]

    def clear_directory_cache(self):
        # type: () -> None
        """Clear the cache of directory placeholder names already created."""
        self._directory_cache = set()

    def list_blobs(self, prefix=''):
        # type: (str) -> Iterator[Blob]
        """List Blobs with the given prefix string (which needn't be a
        "directory" name, and it's relative to the storage_prefix), requesting a
        subset of fields for efficiency. Return a Blob Iterator.
        """
        prefix = os.path.join(self.path_prefix, prefix)
        iterator = self.bucket.list_blobs(prefix=prefix, fields=self.FIELDS)
        return iterator

    def make_dirs(self, sub_path):
        # type: (str) -> None
        """Make sub_path's directory placeholders if they don't exist. E.g. for
        'sim/2020/logs/sim.log', make 'sim/', 'sim/2020/', and 'sim/2020/logs/'.
        See clear_directory_cache().
        """
        parts = os.path.join(self.path_prefix, sub_path).split(os.sep)[:-1]

        for prefix in itertools.accumulate(parts, os.path.join):
            dir_name = os.path.join(prefix, '')

            if dir_name not in self._directory_cache:
                self._directory_cache.add(dir_name)

                blob = self.bucket.blob(dir_name)
                # TODO(jerry): If upload_from_string() took the
                #  `ifGenerationMatch=0` arg that'd create the GCS object if it
                #  doesn't already exist, saving the `exists()` round trip.
                # https://github.com/googleapis/google-cloud-python/issues/10105
                try:
                    if not blob.exists():
                        blob.upload_from_string(b'', content_type=OCTET_STREAM)
                except GoogleCloudError as e:
                    # Failing to create a dir placeholder will affect gcsfuse
                    # mounts but won't break the workflow.
                    logging.exception('Failed to make GCS dir "%s"', dir_name)

    def upload_file(self, local_path, sub_path):
        # type: (str, str) -> bool
        """Upload the file named local_path as (not into) the given GCS sub_path
        (which is relative to the storage_prefix).

        Return True if successful.
        """
        full_path = os.path.join(self.path_prefix, sub_path)

        try:
            self.make_dirs(sub_path)

            blob = self.bucket.blob(full_path)
            blob.upload_from_filename(local_path)  # guesses content_type from the path
        except (GoogleCloudError, FileNotFoundError) as e:
            logging.exception(
                'Failed to upload "%s" as GCS "%s"', local_path, full_path)
            return False
        return True

    def upload_tree(self, local_path, sub_path):
        # type: (str, str) -> bool
        """Upload a file or a directory tree as (not into) the given GCS
        sub_path (which is relative to the storage_prefix).

        Return True if successful.
        """
        if not names_a_directory(sub_path):
            return self.upload_file(local_path, sub_path)

        ok = True
        local_abs = os.path.abspath(local_path)

        for dirpath, dirnames, filenames in os.walk(local_path):
            local_rel_path = os.path.relpath(os.path.abspath(dirpath), local_abs)
            if local_rel_path == '.':
                local_rel_path = ''
            storage_subdir = os.path.join(sub_path, local_rel_path)

            for filename in filenames:
                ok = self.upload_file(
                    os.path.join(dirpath, filename),
                    os.path.join(storage_subdir, filename)) and ok

        return ok

    @classmethod
    def download_blob(cls, blob, local_path):
        # type: (Blob, str) -> bool
        """Download a Blob from GCS as (not into) local_path, making directories
        if needed. `blob` must have its `name` and `bucket` fields set.

        Return True if successful.
        """
        if names_a_directory(local_path):
            fp.makedirs(local_path)
            return True

        fp.makedirs(os.path.dirname(local_path))

        try:
            blob.download_to_filename(local_path)
        except GoogleCloudError as e:
            logging.exception(
                'Failed to download GCS "%s" as "%s"', blob.name, local_path)
            return False

        return True

    def download_file(self, sub_path, local_path):
        # type: (str, str) -> bool
        """Download the GCS file named sub_path (relative to the storage_prefix)
        as (not into) the local_path, making local directories if needed.

        Return True if successful.
        """
        full_path = os.path.join(self.path_prefix, sub_path)
        blob = self.bucket.blob(full_path)
        return self.download_blob(blob, local_path)

    def download_tree(self, sub_path, local_prefix):
        # type: (str, str) -> bool
        """Download all files and directories that begin with the sub_path
        prefix (within the storage_prefix) to their same relative paths in
        local_prefix, making directories if needed.

        Return True if successful.
        """
        if not names_a_directory(sub_path):
            local_path = os.path.join(local_prefix, sub_path)
            return self.download_file(sub_path, local_path)

        ok = True

        for blob in self.list_blobs(sub_path):
            local_rel_path = relpath(blob.name, self.path_prefix)
            path = os.path.join(local_prefix, local_rel_path)
            ok = self.download_blob(blob, path) and ok

        return ok
