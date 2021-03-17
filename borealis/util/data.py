"""Data utilities."""

import datetime
from typing import Any, Dict, Iterable, Mapping, Optional


def select_keys(mapping, keys, **kwargs):
    # type: (Mapping[str, Any], Iterable[str], **Any) -> Dict[str, Any]
    """Return a dict of the selected keys from mapping (if present) plus the
    kwargs.
    """
    result = {key: mapping[key] for key in keys if key in mapping}
    result.update(**kwargs)
    return result


def timestamp(dt=None):
    # type: (Optional[datetime.datetime]) -> str
    """Construct a datetime timestamp from `dt`, default = `now()`."""
    if not dt:
        dt = datetime.datetime.now()

    return dt.strftime('%Y%m%d.%H%M%S')


def format_duration(seconds):
    # type: (float) -> str
    """Format a time duration from seconds to [days] HH:MM:SS. No microseconds."""
    delta = datetime.timedelta(seconds=round(seconds))
    return str(delta)
