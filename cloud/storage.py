"""Interface to Google Cloud Storage (GCS)."""

import itertools
import os
from typing import Iterator, List, Union, Set

from google.cloud.storage import Blob, Bucket, Client
from google.cloud.exceptions import GoogleCloudError

import util.filepath as fp


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


class CloudStorage(object):
    """A higher level interface to a GCS bucket.

    See https://cloud.google.com/storage/docs/naming about legal bucket and
    blob (aka object) names, and note that bucket names are public and must be
    globally unique.
    """

    #: For efficiency, retrieve just these Blob metadata fields.
    FIELDS = 'items(id,name,generation,size),nextPageToken'

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

        # TODO(jerry): Use a service account even when running outside GCE to
        #  avoid that warning? Suppress the warning?
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
                # TODO(jerry): If upload_from_string() accepted an
                #  `ifGenerationMatch=0` arg, that'd create the GCS object if it
                #  doesn't already exist, saving the `exists()` round trip.
                # https://github.com/googleapis/google-cloud-python/issues/10105
                try:
                    if not blob.exists():
                        blob.upload_from_string(b'', content_type=OCTET_STREAM)
                except GoogleCloudError as e:
                    # Failing to create a dir placeholder will affect gcsfuse
                    # mounts but won't break the workflow.
                    # TODO(jerry): Logging
                    print('Failed to make GCS dir "{}": {}'.format(dir_name, e))

    def upload_file(self, local_path, sub_path):
        # type: (str, str) -> bool
        """Upload the file named local_path as (not into) the given GCS sub_path
        (which is relative to the storage_prefix).

        Return True if successful.
        """
        full_path = os.path.join(self.path_prefix, sub_path)

        try:
            self.make_dirs(sub_path)

            print('Uploading "{}" to GCS "{}"'.format(local_path, full_path))  # *** DEBUG ***
            blob = self.bucket.blob(full_path)
            blob.upload_from_filename(local_path)  # guesses content_type from the path
        except (GoogleCloudError, FileNotFoundError) as e:
            # TODO(jerry): Logging
            print('Failed to upload "{}" as GCS "{}": {}'.format(local_path, full_path, e))
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
        """Download a Blob from GCS as (not into) the local_path, making local
        directories if needed.

        Return True if successful.
        """
        if names_a_directory(local_path):
            fp.makedirs(local_path)
            return True

        fp.makedirs(os.path.dirname(local_path))

        try:
            print('Downloading GCS "{}" to "{}"'.format(blob.name, local_path))  # *** DEBUG ***
            blob.download_to_filename(local_path)
        except GoogleCloudError as e:
            print('Failed to download GCS "{}" as "{}": {}'.format(
                blob.name, local_path, e))
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

    def download_tree(self, sub_path, local_path):
        # type: (str, str) -> bool
        """Download a file or directory tree as (not into) the local_path,
        making directories if needed.

        Return True if successful.
        """
        if not names_a_directory(sub_path):
            return self.download_file(sub_path, local_path)

        ok = True

        for blob in self.list_blobs(sub_path):
            local_rel_path = os.path.relpath(blob.name, self.path_prefix)
            path = os.path.join(local_path, local_rel_path)
            ok = self.download_blob(blob, path) and ok

        return ok
