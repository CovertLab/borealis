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

from cloud.storage import CloudStorage, names_a_directory
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
    #   NOTE: Each path in `inputs` and `outputs` names a directory tree of
    #   files if it ends with '/', otherwise a file. This is needed because the
    #   GCS is a flat object store without directories and DockerTask needs to
    #   know whether to create files or directories.
    #
    #   If the task completes normally, DockerTask will all its outputs to GCS.
    #   Otherwise, it only writes '>>' log files.
    #
    #   An output path that starts with '>>' will capture a log of stdout +
    #   stderr + other log messages like elapsed time and task exit code.
    #   DockerTask will write it even if the task fails (to aid debugging),
    #   unlike all the other outputs.
    #
    #   An output path that starts with '>' captures stdout + stderr. The rest
    #   of the path is as if internal to the container, and will get rebased to
    #   to compute its storage path.
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
        rel_path = os.path.relpath(core_path, internal_prefix)
        new_path = os.path.join(new_prefix, rel_path)

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
        """Create a path mapping between a path internal to the Docker container
        and one in the local file system, make the Docker Mount, and create the
        local file or directory so Docker can detect whether to mount a file or
        directory.
        """
        local_path = self.rebase(internal_path, local_prefix)
        storage_path = self.rebase(internal_path, '')  # CloudStorage handles the storage_prefix

        fp.makedirs(os.path.dirname(local_path))
        if not names_a_directory(local_path):
            open(local_path, 'a').close()

        # Create the Docker Mount unless this mapping will capture stdout.
        mount = (None if captures(internal_path)
                 else Mount(target=internal_path, source=local_path, type='bind'))

        return PathMapping(internal_path, local_path, storage_path, mount)

    def setup_mounts(self, group):
        # type: (str) -> List[PathMapping]
        """Set up all the mounts for the 'inputs' or 'outputs' group."""
        return [self.setup_mount(path, os.path.join(self.LOCAL_BASEDIR, group))
                for path in self.get(group, [])]

    def _outputs_to_push(self, lines, success, outs):
        # type: (List[str], bool, List[PathMapping]) -> List[PathMapping]
        """Write requested stdout+stderr and log output files, then return a
        list of all output PathMappings to push to GCS. That's all of them if
        the Task succeeded, or just the '>>' logs if it failed.
        """
        to_push = []

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
                to_push.append(out)

        return to_push

    def push_to_gcs(self, to_push):
        # type: (List[PathMapping]) -> bool
        """Push outputs to GCS. Return True if successful."""
        # TODO(jerry): Parallelize.
        ok = True
        gcs = CloudStorage(self['storage_prefix'])

        for mapping in to_push:
           ok = gcs.upload_tree(mapping.local, mapping.storage) and ok

        return ok

    def pull_from_gcs(self, to_pull):
        # type: (List[PathMapping]) -> bool
        """Pull inputs from GCS. Return True if successful."""
        # TODO(jerry): Parallelize.
        ok = True
        gcs = CloudStorage(self['storage_prefix'])

        for mapping in to_pull:
            ok = gcs.download_tree(mapping.storage, mapping.local) and ok

        return ok


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
        # TODO(jerry): Push the log file to GCS even if there's a Docker error.
        # TODO(jerry): StackDriver logging.
        # TODO(jerry): Implement timeouts.
        # TODO(jerry): Parallelize Docker pull with pulling inputs.
        errors = []
        def check(success, or_error):
            if not success:
                errors.append(or_error)

        print('Starting task "{}"'.format(self['name']))

        docker_client = docker.from_env()
        ins = self.setup_mounts('inputs')
        outs = self.setup_mounts('outputs')

        repository, tag = parse_repository_tag(self['image'])
        if not tag:
            tag = 'latest'  # 'latest' is the default tag; it doesn't mean squat
        image = docker_client.images.pull(repository, tag)
        lines = []  # type: List[str]

        try:
            check(self.pull_from_gcs(ins), 'Failed to pull inputs')

            container = docker_client.containers.run(
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
                check(exit_code == 0, 'Exit code {}'.format(exit_code))
                print('Exit code: {}'.format(exit_code))  # TODO(jerry): Log more info
            finally:
                try:
                    container.remove(force=True)
                except docker_errors.APIError as e:
                    print('Docker error removing a container: {}'.format(e))

            to_push = self._outputs_to_push(lines, not errors, outs)
            # NOTE: The log file was already written and might fail to push, so
            # it won't report on push failures.
            check(self.push_to_gcs(to_push), 'Failed to push outputs')

            if errors:
                return FWAction(
                    exit=True,  # skip remaining Firetasks in this Firework
                    defuse_children=True,  # skip downstream FireWorks
                    stored_data={'errors': errors})  # final report

        finally:
            wipe_out = self.LOCAL_BASEDIR
            # [Could wipe just os.path.join(self.LOCAL_BASEDIR, 'inputs') to
            # keep the outputs for local scrutiny.]
            shutil.rmtree(wipe_out, ignore_errors=True)

        return None
