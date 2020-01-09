"""A Firetask that runs a shell command in a Docker container, pulling input
files from Google Cloud Storage (GCS) and pushing output files to GCS.

TODO: Split out a GCS pull/push Firetask?

TODO: An option to keep all the local files in an 'out/' directory instead of or
in addition to writing them to a GCS bucket.

Parms:
`name` is a task name for logs and such.

`image` is the Docker image to pull.

`command` is the command tokens to run inside the Docker container.

`inputs` and `outputs` are expressed as absolute paths internal to the Docker
container. Their corresponding GCS storage paths will get constructed by
rebasing each path from `internal_prefix` to `storage_prefix`, and their
corresponding local paths outside the container will get constructed by rebasing
each path to `local_prefix`.

Each path indicates a file or (if it ends with '/') a directory tree of files to
fetch or store.

Outputs will get written to GCS if the task completes normally. An output path
that starts with '>' will capture stdout + stderr (if the task completes
normally), while the rest of the path gets rebased to provide the storage path.

An output path that starts with '>>' will capture a log of stdout + stderr +
other log messages like elapsed time and task exit code, even if the task fails.
This is useful for debugging.

`timeout` in seconds indicates how long to let the task run.
"""

from __future__ import absolute_import, division, print_function

from collections import namedtuple
import os
import shutil
from typing import List, Optional

import docker
from docker import errors as docker_errors
from docker.types import Mount
from docker.utils import parse_repository_tag
from fireworks import explicit_serialize, FiretaskBase, FWAction

import util.filepath as fp


def uid_gid():
    """Return the Unix uid:gid (user ID, group ID) pair."""
    return '{}:{}'.format(fp.run_cmdline('id -u'), fp.run_cmdline('id -g'))

PathMapping = namedtuple('PathMapping', 'internal local storage mount')


def captures(path):
    # type: (str) -> Optional[str]
    """Categorize the given output path as capturing a log (>>), capturing
    just stdout + stderr (>), or neither (a regular file or directory).
    """
    return ('>>' if path.startswith('>>')
            else '>' if path.startswith('>')
    else None)


def names_a_directory(path):
    # type: (str) -> bool
    """Return True if the given path names a directory vs. a file (even on GCS,
    existing or yet to be created) by checking if the path ends with a '/'.
    """
    return path.endswith(os.sep)


@explicit_serialize
class DockerTask(FiretaskBase):
    _fw_name = "DockerTask"

    required_params = [
        'name',
        'image',
        'command',
        'internal_prefix',
        'storage_prefix']
    optional_params = [
        'inputs',
        'outputs',
        'timeout']

    LOCAL_BASEDIR = os.path.join(os.sep, 'tmp', 'fireworker')

    def rebase(self, internal_path, new_prefix):
        # type: (str, str) -> str
        """Rebase an internal input or output path from the internal_prefix to
        new_prefix (without any '>' or '>>' sigil).

        A path starting with '>' or '>>' means capture stdout + stderr for
        writing to the storage path. '>>' creates a log of stdout + stderr +
        additional information and writes it even if the Docker command fails.

        A path ending with '/' identifies a directory.
        """
        core_path = internal_path.lstrip('>')
        internal_prefix = self['internal_prefix']
        relpath = os.path.relpath(core_path, internal_prefix)
        new_path = os.path.join(new_prefix, relpath)

        # os.path.relpath() removes a trailing slash. Restore it.
        if core_path.endswith(os.sep):
            new_path = os.path.join(new_path, '')

        if '..' in new_path:
            # This could happen if `internal_path` doesn't start with
            # `internal_prefix`.
            raise ValueError('Rebased path "{}" contains ".."'.format(new_path))
        return new_path

    def setup_mount(self, internal_path, local_prefix):
        # type: (str, str) -> PathMapping
        """Set up the Docker Mount between a path internal to the Docker
        container and one in the local file system, and create the local file or
        directory so Docker can detect whether to mount a file or directory.
        """
        local_path = self.rebase(internal_path, local_prefix)
        storage_path = self.rebase(internal_path, self['storage_prefix'])

        if names_a_directory(local_path):
            fp.makedirs(local_path)
        else:
            fp.makedirs(os.path.dirname(local_path))
            open(local_path, 'a').close()

        # Create the Docker Mount unless this mapping will capture stdout, etc.
        mount = (None if captures(internal_path)
                 else Mount(target=internal_path, source=local_path, type='bind'))

        return PathMapping(internal_path, local_path, storage_path, mount)

    def setup_mounts(self, group):
        # type: (str) -> List[PathMapping]
        """Set up all the mounts for the 'inputs' or 'outputs' group."""
        return [self.setup_mount(path, os.path.join(self.LOCAL_BASEDIR, group))
                for path in self.get(group, [])]

    # ODDITIES ABOUT THE PYTHON DOCKER PACKAGE
    #
    # images.pull() will pull a list of images if neither arg gives a tag. We
    # don't want that, so provide a default tag if the image name doesn't
    # include one.
    #
    # Some variations on the call sequence bury the exit code and stdout, so
    # test carefully when changing it and remove the container manually.
    #
    # Mounts need to be set up just right. Use type='bind' and pre-create the
    # local file or directory.
    #
    # Example container.attrs['State'] (if it is a dict):
    #   {'Dead': False,
    #    'Error': '',
    #    'ExitCode': 0,        # always seems to be 0!
    #    'FinishedAt': '0001-01-01T00:00:00Z',
    #    'OOMKilled': False,
    #    'Paused': False,
    #    'Pid': 0,
    #    'Restarting': False,
    #    'Running': False,
    #    'StartedAt': '0001-01-01T00:00:00Z',
    #    'Status': 'created'}  # always seems to be 'created'!
    #
    # Examples of container.wait() results:
    #   {'Error': None, 'StatusCode': 0}
    #   {'Error': None, 'StatusCode': 1}

    def run_task(self, fw_spec):
        """Run a task as a shell command in a Docker container."""
        # TODO(jerry): Detect failures, pull/push to GCS, StackDriver, timeout.
        print('Starting task "{}"'.format(self['name']))

        client = docker.from_env()
        ins = self.setup_mounts('inputs')
        outs = self.setup_mounts('outputs')

        repository, tag = parse_repository_tag(self['image'])
        if not tag:
            tag = 'latest'  # 'latest' is the default tag; it doesn't mean squat
        image = client.images.pull(repository, tag)
        lines = []  # stdout+stderr
        exit_code = -1

        try:
            container = client.containers.run(
                image,
                command=self['command'],
                user=uid_gid(),
                mounts=[mapping.mount for mapping in ins + outs if mapping.mount],
                detach=True)
            # TODO: Catch docker_errors.ImageNotFound, docker_errors.APIError.

            try:
                for line in container.logs(stream=True):  # TODO: Set follow=True?
                    # NOTE: Can call stream.close() to cancel from another thread.
                    lines.append(line)
                    print(line.decode().rstrip())

                exit_code = container.wait()['StatusCode']
                print('Exit code: {}'.format(exit_code))  # TODO(jerry): Log more info
            finally:
                try:
                    container.remove(force=True)
                except docker_errors.APIError as e:
                    print('Docker error removing a container: {}'.format(e))

            # TODO(jerry): Construct the '>>' log file if requested and push to GCS.
            #  NOTE: file.writelines(lines) doesn't add newlines.

            if exit_code != 0:
                # The task failed. Skip downstream Firetasks and FireWorks.
                return FWAction(exit=True, defuse_children=True)

            # TODO(jerry): Write the '>' log file if requested.
            # TODO(jerry): Push outputs back to GCS.

        finally:
            shutil.rmtree(self.LOCAL_BASEDIR, ignore_errors=True)
            # TODO(jerry): More cleanup?

        return None
