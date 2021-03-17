"""File and path utilities."""

import logging
import os
import subprocess
from typing import Optional, Sequence, Tuple


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

    if full_path:
        os.makedirs(full_path, exist_ok=True)
    return full_path


def run_cmd2(tokens, trim=True, timeout=TIMEOUT):
    # type: (Sequence[str], bool, Optional[int]) -> Tuple[str, str]
    """Run a shell command-line (in token list form) and return a tuple
    containing its (stdout, stderr).
    This does not expand filename patterns or environment variables or do other
    shell processing steps.

    Args:
        tokens: The command line as a list of string tokens.
        trim: Whether to trim off trailing whitespace. This is useful
            because the outputs usually end with a newline.
        timeout: timeout in seconds; None for no timeout.
    Returns:
        The command's stdout and stderr strings.
    Raises:
        OSError (e.g. FileNotFoundError [Python 3] or PermissionError),
          subprocess.SubprocessError (TimeoutExpired or CalledProcessError)
    """
    out = subprocess.run(
        tokens,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        encoding='utf-8',
        timeout=timeout)
    if trim:
        return out.stdout.rstrip(), out.stderr.rstrip()
    return out.stdout, out.stderr


def run_cmd(tokens, trim=True, timeout=TIMEOUT):
    # type: (Sequence[str], bool, Optional[int]) -> str
    """Run a shell command-line (in token list form) and return its stdout.
    See run_cmd2().
    """
    return run_cmd2(tokens, trim=trim, timeout=timeout)[0]


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
    except (OSError, subprocess.SubprocessError):
        logging.exception('Failed to run command line: %s', line)
        return None
