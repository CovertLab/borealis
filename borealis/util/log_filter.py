"""Python logging filtering."""

import logging
from typing import Dict


class LogPrefixFilter(logging.Filter):
    """Filter log records by a specific log level for each name prefix. (The
    prefix is the first component of the dotted log name.)
    """
    # Subclass logging.Filter just to satisfy addFilter()'s zealous type decl.

    def __init__(self, levels, else_level):
        # type: (Dict[str, int], int) -> None
        """
        levels: a dictionary of log name prefix -> log level.
        else_level: the default log level to use.
        """
        super(LogPrefixFilter, self).__init__()
        self.levels = levels
        self.else_level = else_level

    def filter(self, record):
        # type: (logging.LogRecord) -> bool
        """Return False to reject this log record; True to pass it to other
        filters.
        """
        prefix = record.name.split('.', 1)[0]
        filter_level = self.levels.get(prefix, self.else_level)
        return record.levelno >= filter_level