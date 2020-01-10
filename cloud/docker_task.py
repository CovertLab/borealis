"""A Firetask that runs a shell command in a Docker container, pulling input
files from Google Cloud Storage (GCS) and pushing output files to GCS.

TODO: An option to keep all the local files in an 'out/' directory instead of or
in addition to writing them to a GCS bucket.
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

    # Parms
    # -----
    # name: a task name for logs and such.
    #
    # image: the Docker image to pull.
    #
    # command: the command tokens to run inside the Docker container.
    #
    # internal_prefix: the base pathname inside the Docker container for inputs
    #   and outputs.
    #
    # storage_prefix: the base pathname in GCS for inputs and outputs.
    #
    # inputs, outputs: absolute pathnames internal to the Docker container of
    #   input/output files and directories to pull/push to GCS. DockerTask will
    #   construct the corresponding GCS storage paths by rebasing each path from
    #   `internal_prefix` to `storage_prefix`, and the corresponding local paths
    #   outside the container by rebasing each path to `local_prefix`.
    #
    #   Each path in `inputs` and `outputs` indicates a directory tree of files
    #   if it ends with '/', otherwise a file.
    #
    #   If the task completes normally, DockerTask will all its outputs to GCS.
    #   Otherwise, it only writes '>>' log files.
    #
    #   An output path that starts with '>' captures stdout + stderr. The rest
    #   of that pathname provides a pathname as if internal to the container,
    #   which gets rebased to compute its local and storage pathnames.
    #
    #   An output path that starts with '>>' will capture a log of stdout +
    #   stderr + other log messages like elapsed time and task exit code.
    #   DockerTask will write it even if the task failed, to aid debugging.
    #
    # timeout: in seconds, indicates how long to let the task run.
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

    def _outputs_to_save(self, lines, success, outs):
        # type: (List[str], bool, List[PathMapping]) -> List[PathMapping]
        """Write requested stdout+stderr and log output files, then return a
        list of all output PathMappings to save to GCS: everything if the Task
        succeeded; just the '>>' logs if it failed.
        """
        to_save = []

        for out in outs:
            cap = captures(out.internal)
            if cap:
                try:
                    with open(out.local, 'w') as f:
                        # TODO(jerry): If cap = '>>', include prologue and epilogue.
                        f.writelines(lines)
                except IOError as e:
                    print('Error writing to {}: {}'.format(out.internal, e))

            if success or cap == '>>':
                to_save.append(out)

        return to_save

    def push_to_gcs(self, to_save):
        # type: (List[PathMapping]) -> None
        """Push outputs to GCS."""
        # TODO: Call the API instead of gsutil? That'll let us create the psuedo
        #  directory placeholders needed for fast gcsfuse, but we won't get
        #  parallel operations and retry handling for free. If we stick with
        #  gsutil, make this more careful about which paths to upload and deal
        #  with gsutil exit status.
        if len(to_save) < 1:
            return

        if len(to_save) == 1:  # e.g. just a >>log file, not all of base/outputs/
            mapping = to_save[0]
            fp.run_cmd(['gsutil', '-m', 'cp', '-r', mapping.local, 'gs://' + mapping.storage])
            return

        local_root = os.path.join(self.LOCAL_BASEDIR, 'outputs', '*')
        storage_prefix = self['storage_prefix']
        fp.run_cmd(['gsutil', '-m', 'cp', '-r', local_root, 'gs://' + storage_prefix])

    def pull_from_gcs(self, ins):
        # type: (List[PathMapping]) -> None
        """Pull inputs from GCS."""
        # TODO(jerry): Handle errors, further parallelize, and maybe do retries.
        for mapping in ins:
            fp.run_cmd(['gsutil', '-m', 'cp', '-r', 'gs://' + mapping.storage, mapping.local])


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
        # TODO(jerry): Push the log file to GCS even if there's a Docker error.
        print('Starting task "{}"'.format(self['name']))

        client = docker.from_env()
        ins = self.setup_mounts('inputs')
        outs = self.setup_mounts('outputs')

        repository, tag = parse_repository_tag(self['image'])
        if not tag:
            tag = 'latest'  # 'latest' is the default tag; it doesn't mean squat
        image = client.images.pull(repository, tag)
        lines = []  # type: List[str]
        exit_code = -1

        try:
            self.pull_from_gcs(ins)

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
                    line = line.decode()
                    lines.append(line)
                    print(line.rstrip())

                exit_code = container.wait()['StatusCode']
                print('Exit code: {}'.format(exit_code))  # TODO(jerry): Log more info
            finally:
                try:
                    container.remove(force=True)
                except docker_errors.APIError as e:
                    print('Docker error removing a container: {}'.format(e))

            to_save = self._outputs_to_save(lines, exit_code == 0, outs)
            self.push_to_gcs(to_save)

            if exit_code != 0:
                # The task failed so skip downstream Firetasks and FireWorks.
                return FWAction(exit=True, defuse_children=True)

        finally:
            wipe_out = self.LOCAL_BASEDIR
            # wipe_out = os.path.join(self.LOCAL_BASEDIR, 'inputs')
            shutil.rmtree(wipe_out, ignore_errors=True)

        return None
