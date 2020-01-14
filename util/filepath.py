"""File name and path utilities."""

from __future__ import absolute_import, division, print_function

import errno
import os
import subprocess
from typing import Optional, Sequence


TIMEOUT = 60  # seconds

def makedirs(path, *paths):
    # type: (str, *str) -> str
    """Join one or more path components, make that directory path (using the
    default mode 0o0777), and return the joined path.

    Raise OSError if it can't achieve the result (e.g. the containing directory
    is readonly or the path contains a file); not if the directory already
    exists.
    """
    full_path = os.path.join(path, *paths)

    try:
        if full_path:
            os.makedirs(full_path)
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(full_path):
            raise

    return full_path


def run_cmd(tokens, trim=True, timeout=TIMEOUT):
    # type: (Sequence[str], bool, Optional[int]) -> str
    """Run a shell command-line (in token list form) and return its output.
    This does not expand filename patterns or environment variables or do other
    shell processing steps.

    Args:
        tokens: The command line as a list of string tokens.
        trim: Whether to trim off trailing whitespace. This is useful
            because the subprocess output usually ends with a newline.
        timeout: timeout in seconds; None for no timeout.
    Returns:
        The command's output string.
    Raises:
        OSError, subprocess.SubprocessError (TimeoutExpired or CalledProcessError)
    """
    out = subprocess.run(
        tokens, stdout=subprocess.PIPE, check=True, universal_newlines=True,
        timeout=timeout).stdout
    if trim:
        out = out.rstrip()
    return out


def run_cmdline(line, trim=True, timeout=TIMEOUT):
    # type: (str, bool, Optional[int]) -> Optional[str]
    """Run a shell command-line string and return its output, or None if it
    failed. This does not expand filename patterns or environment variables or
    do other shell processing steps like quoting.

    Args:
        line: The command line as a string to split.
        trim: Whether to trim off trailing whitespace. This is useful
            because the subprocess output usually ends with a newline.
        timeout: timeout in seconds; None for no timeout.
    Returns:
        The command's output string, or None if it couldn't even run.
    """
    try:
        return run_cmd(tokens=line.split(), trim=trim, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        print('failed to run command line {}: {}'.format(line, e))
        return None
