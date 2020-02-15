"""Data utilities."""

from __future__ import absolute_import, division, print_function

from typing import Any, Dict, Iterable, Mapping


def select_keys(mapping, keys, **kwargs):
    # type: (Mapping[str, Any], Iterable[str], **Any) -> Dict[str, Any]
    """Return a dict of the selected keys from mapping (if present) plus the
    kwargs.
    """
    result = {key: mapping[key] for key in keys if key in mapping}
    result.update(**kwargs)
    return result
