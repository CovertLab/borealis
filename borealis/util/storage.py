"""Interface to Google Cloud Storage (GCS)."""

import logging
import os
from typing import Iterator, List, Optional, Set

# noinspection PyPackageRequirements
from google.cloud.storage import Blob, Client
# noinspection PyPackageRequirements
from google.cloud.exceptions import GoogleCloudError, PreconditionFailed

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
        Logs Writer
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
    #: Needs 'nextPageToken' to iterate through all the entries.
    FIELDS = 'items(bucket,name,id,generation,size),nextPageToken'

    def __init__(self, storage_prefix):
        # type: (str) -> None
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

    def __repr__(self) -> str:
        return '{}({!r}, {!r})'.format(
            self.__class__.__name__, self.bucket_name, self.path_prefix)

    def url(self, *path_elements: str) -> str:
        """Return a gs:// URL for the given path relative to the storage_prefix."""
        return os.path.join('gs://', self.bucket_name, self.path_prefix, *path_elements)

    def clear_directory_cache(self):
        # type: () -> None
        """Clear the cache of directory placeholder names already created."""
        self._directory_cache = set()

    def list_blobs(self, prefix='', star=False):
        # type: (str, bool) -> Iterator[Blob]
        """List Blobs that have the given prefix string with optional '*' glob.

        Arguments:
            prefix: A pathname prefix appended to storage_prefix. It needn't be
                a whole "subdirectory" name; it's just a prefix.

            star: Match the glob pattern "prefix*" within one "directory" level,
                as if GCS had directories.

                `*` matches 0 or more characters up through a `/`, naming
                stored Blobs and virtual "subdirectories" that are prefixes for
                Blob names.

                If `prefix` ends with a '/', this will list it (if it exists as
                a "dir") along with its immediate "files" and "subdirs".

        Returns:
            a Blob Iterator. For speed, each Blob has a subset of the possible
                fields.
        """
        prefix = os.path.join(self.path_prefix, prefix)
        iterator = self.client.list_blobs(
            self.bucket,
            prefix=prefix,
            fields=self.FIELDS,
            delimiter=os.sep if star else None,
            include_trailing_delimiter=True if star else None)
        return iterator

    def make_dirs(self, sub_path):
        # type: (str) -> None
        """Make sub_path's directory placeholders if they don't exist. E.g. for
        'sim/2020/logs/sim.log', make 'sim/', 'sim/2020/', and 'sim/2020/logs/'.
        See clear_directory_cache().
        """
        parts = os.path.join(self.path_prefix, sub_path).split(os.sep)[:-1]
        dir_name = ''

        for subdir in parts:
            dir_name = os.path.join(dir_name, subdir, '')

            if dir_name not in self._directory_cache:
                self._directory_cache.add(dir_name)

                blob = self.bucket.blob(dir_name)
                try:
                    # if_generation_match=0: upload if absent, fail if present.
                    blob.upload_from_string(
                        b'', content_type=OCTET_STREAM, if_generation_match=0)
                except PreconditionFailed:  # the blob is already present
                    pass
                except GoogleCloudError:
                    # Failing to create a dir placeholder will affect gcsfuse
                    # mounts but won't break the workflow.
                    logging.exception('Failed to make GCS dir "%s"', dir_name)

    def upload_file(self, local_path, sub_path):
        # type: (str, str) -> bool
        """Upload the file named local_path as (not into) the given GCS sub_path
        (which is relative to the storage_prefix).

        Return True if successful. Logs exceptions.
        """
        full_path = os.path.join(self.path_prefix, sub_path)

        try:
            self.make_dirs(sub_path)

            blob = self.bucket.blob(full_path)
            blob.upload_from_filename(local_path)  # guesses content_type from the path
        except (GoogleCloudError, OSError):
            logging.exception(
                'Failed to upload "%s" as GCS "%s"', local_path, full_path)
            return False
        return True

    def upload_tree(self, local_path, sub_path):
        # type: (str, str) -> bool
        """Upload a file or a directory tree as (not into) the given GCS
        sub_path (which is relative to the storage_prefix).

        Return True if successful. Logs exceptions.
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

        Return True if successful. Logs exceptions.
        """
        if names_a_directory(local_path):
            fp.makedirs(local_path)
            return True

        fp.makedirs(os.path.dirname(local_path))

        try:
            blob.download_to_filename(local_path)
        except GoogleCloudError:
            logging.exception(
                'Failed to download GCS "%s" as "%s"', blob.name, local_path)
            return False

        return True

    def download_file(self, sub_path, local_path):
        # type: (str, str) -> bool
        """Download the GCS file named sub_path (relative to the storage_prefix)
        as (not into) the local_path, making local directories if needed.

        Return True if successful. Logs exceptions.
        """
        full_path = os.path.join(self.path_prefix, sub_path)
        blob = self.bucket.blob(full_path)
        return self.download_blob(blob, local_path)

    def download_tree(self, sub_path, local_prefix):
        # type: (str, str) -> bool
        """Download all files and directories that begin with the sub_path
        prefix (within the storage_prefix) to their same relative paths in
        local_prefix, making directories if needed.

        Return True if successful. Logs exceptions.
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
