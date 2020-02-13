"""A Firetask that runs a shell command in a Docker container, pulling input
files from Google Cloud Storage (GCS) and pushing output files to GCS.
"""

from __future__ import absolute_import, division, print_function

from collections import namedtuple
import logging
import os
from pprint import pprint
import shutil
from typing import Any, List, Optional

import docker
from docker import errors as docker_errors
from docker.types import Mount
from docker.utils import parse_repository_tag
from fireworks import explicit_serialize, FiretaskBase, FWAction

import borealis.util.filepath as fp
import borealis.util.storage as st


class DockerTaskError(Exception):
    pass


PathMapping = namedtuple('PathMapping', 'captures local_prefix local sub_path mount')


def uid_gid():
    """Return the Unix uid:gid (user ID, group ID) pair."""
    return '{}:{}'.format(fp.run_cmdline('id -u'), fp.run_cmdline('id -g'))


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
    _fw_name = 'DockerTask'

    # Parms
    # -----
    # name: the payload task name, for logging.
    #
    # image: the Docker Image to pull.
    #
    # command: the shell command tokens to run in the Docker Container.
    #
    # internal_prefix: the base pathname inside the Docker Container for inputs
    #   and outputs (files and directory trees).
    #
    # storage_prefix: the GCS base pathname for inputs and outputs.
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

    def _log(self):
        # type: () -> logging.Logger
        """Return a Logger for this task."""
        parent = logging.getLogger('dockerfiretask')
        parent.setLevel(logging.DEBUG)

        name = 'dockerfiretask.{}'.format(self['name'])
        return logging.getLogger(name)

    def pull_docker_image(self, docker_client):
        # type: (docker.DockerClient) -> Any  # a Docker Image
        """Pull the requested Docker Image. Ensure there's a tag so pull() will
        get one Image rather than all tags in a repository.
        """
        repository, tag = parse_repository_tag(self['image'])
        if not tag:
            tag = 'latest'  # 'latest' is the default tag; it doesn't mean squat
        self._log().info('Pulling Docker image %s:%s', repository, tag)
        return docker_client.images.pull(repository, tag)

    def rebase(self, internal_path, new_prefix):
        # type: (str, str) -> str
        """Strip off any '>' or '>>' prefix then rebase the internal-to-container
        path from the internal_prefix to new_prefix.

        '>' or '>>' means capture stdout + stderr rather than fetching a
        container file; the rest of internal_path is the as-if-internal path.
        '>>' creates a log of stdout + stderr + additional information and
        writes it even if the Docker command fails.

        A path ending with '/' indicates a directory.
        """
        core_path = internal_path.lstrip('>')
        internal_prefix = self['internal_prefix']
        rel_path = st.relpath(core_path, internal_prefix)
        new_path = os.path.join(new_prefix, rel_path)

        if '..' in new_path:
            # This could happen if `internal_path` doesn't start with
            # `internal_prefix`.
            raise ValueError('Rebased path "{}" contains ".."'.format(new_path))
        return new_path

    def setup_mount(self, internal_path, local_prefix):
        # type: (str, str) -> PathMapping
        """Create a PathMapping between a path internal to the Docker container
        and a sub_path relative the storage_prefix (GCS) and the local_prefix
        (local file system), make the Docker local:internal Mount object, and
        create the local file or directory so Docker can detect whether to mount
        a file or directory.
        """
        local_path = self.rebase(internal_path, local_prefix)
        sub_path = self.rebase(internal_path, '')

        fp.makedirs(os.path.dirname(local_path))
        if not st.names_a_directory(local_path):
            open(local_path, 'a').close()

        # Create the Docker Mount unless this mapping will capture stdout & stderr.
        caps = captures(internal_path)
        mount = (None if caps
                 else Mount(target=internal_path, source=local_path, type='bind'))

        return PathMapping(caps, local_prefix, local_path, sub_path, mount)

    def setup_mounts(self, group):
        # type: (str) -> List[PathMapping]
        """Set up all the mounts for the 'inputs' or 'outputs' group."""
        return [self.setup_mount(path, os.path.join(self.LOCAL_BASEDIR, group))
                for path in self.get(group, [])]

    def _outputs_to_push(self, lines, success, outs, epilogue):
        # type: (List[str], bool, List[PathMapping], str) -> List[PathMapping]
        """Write requested stdout+stderr and log output files, then return a
        list of all output PathMappings to push to GCS. That's all of them if
        the Task succeeded; only the '>>' logs if it failed.
        """
        to_push = []

        for out in outs:
            if out.captures:
                try:
                    with open(out.local, 'w') as f:
                        hr = ''
                        if out.captures == '>>':
                            hr = '-' * 80
                            pprint(self.to_dict(), f)  # prologue
                            f.write('\n{}\n'.format(hr))

                        f.writelines(lines)

                        if hr:
                            f.write('{}\n\n{}\n'.format(hr, epilogue))
                except IOError as e:
                    self._log().exception('Error capturing to %s', out.local)

            if success or out.captures == '>>':
                to_push.append(out)

        return to_push

    def push_to_gcs(self, to_push):
        # type: (List[PathMapping]) -> bool
        """Push outputs to GCS. Return True if successful."""
        ok = True
        prefix = self['storage_prefix']

        self._log().info('Pushing %s outputs to GCS %s: %s',
            len(to_push), prefix, [mapping.sub_path for mapping in to_push])
        gcs = st.CloudStorage(prefix)

        for mapping in to_push:
           ok = gcs.upload_tree(mapping.local, mapping.sub_path) and ok

        return ok

    def pull_from_gcs(self, to_pull):
        # type: (List[PathMapping]) -> bool
        """Pull inputs from GCS. Return True if successful."""
        ok = True
        prefix = self['storage_prefix']

        self._log().info('Pulling %s inputs from GCS %s: %s',
            len(to_pull), prefix, [mapping.sub_path for mapping in to_pull])
        gcs = st.CloudStorage(prefix)

        for mapping in to_pull:
            ok = gcs.download_tree(mapping.sub_path, mapping.local_prefix) and ok

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
        # type: (dict) -> Optional[FWAction]
        """Run a task as a shell command in a Docker container."""
        name = self['name']
        errors = []  # type: List[str]
        lines = []  # type: List[str]
        logger = self._log()

        def check(success, or_error):
            if not success:
                errors.append(or_error)

        def epilog():
            # TODO(jerry): Include the elapsed time and the timeout parameter.
            return '{} task: {} {}'.format(
                'FAILED' if errors else 'SUCCESSFUL', name, errors if errors else '')

        logger.warning('STARTING TASK: %s', name)

        try:
            docker_client = docker.from_env()
            image = self.pull_docker_image(docker_client)

            ins = self.setup_mounts('inputs')
            outs = self.setup_mounts('outputs')

            check(self.pull_from_gcs(ins), 'Failed to pull inputs')

            logger.info('Running: %s', self['command'])
            container = docker_client.containers.run(
                image,
                command=self['command'],
                user=uid_gid(),
                mounts=[mapping.mount for mapping in ins + outs if mapping.mount],
                detach=True)

            try:
                for line in container.logs(stream=True):  # TODO: Set follow=True?
                    # NOTE: Can call stream.close() to cancel from another thread.
                    line = line.decode()
                    lines.append(line)
                    logger.info('%s', line.rstrip())

                exit_code = container.wait()['StatusCode']
                check(exit_code == 0, 'Exit code {}{}'.format(
                    exit_code, ' (SIGKILL)' if exit_code == 137 else ''))
                state = container.attrs.get('State')
                if isinstance(state, dict):
                    check(not state.get('OOMKilled'), 'OOM-Killed')
            finally:
                try:
                    container.remove(force=True)
                except docker_errors.APIError as e:  # troubling but not a task error
                    logger.exception('Docker error removing a container')

            to_push = self._outputs_to_push(lines, not errors, outs, epilog())

            # NOTE: The >>task.log file won't report push failures since it's
            # written before pushing and might itself fail to push. But the
            # StackDriver log will get it, and the Fireworks stored_data will
            # get it if this returns FWAction rather than raise an exception.
            check(self.push_to_gcs(to_push), 'Failed to push outputs')

        except (Exception, KeyboardInterrupt) as e:
            # Log it, clean up, and re-raise it. That'll FIZZLE the Firework.
            check(False, repr(e))
            raise
        finally:
            logger.warning('%s', epilog())

            # [Could wipe just os.path.join(self.LOCAL_BASEDIR, 'inputs') to
            # keep the outputs for local scrutiny.]
            wipe_out = self.LOCAL_BASEDIR
            shutil.rmtree(wipe_out, ignore_errors=True)

        if errors:
            raise DockerTaskError(repr(errors))  # FIZZLE this Firework

        return None
