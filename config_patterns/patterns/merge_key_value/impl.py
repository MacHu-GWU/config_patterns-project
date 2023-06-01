# -*- coding: utf-8 -*-

"""
In configuration management, it is common practice to divide the configuration
into multiple files. From a machine's perspective, merging multiple dictionary data
into one can be more convenient to process it later. This module is designed to
recursively merge two dictionaries or a list of dictionaries.
"""

import typing as T
import copy


def merge_key_value(
    data1: dict,
    data2: dict,
    _fullpath: T.Optional[str] = None,
) -> dict:
    """
    Merge two dict recursively. Both dict are equally important.
    Note that the original data will NOT be modified, it copy the data
    and return a new dict (the merged one).

    :param data1: dict data 1.
    :param data2: dict data 2.

    Example::

        >>> data1 = {
        ...     "key1": "value1",
        ...     "credentials": [
        ...         {"username": "alice"},
        ...         {"username": "bob"},
        ...     ]
        ... }
        >>> data2 = {
        ...     "key2": "value2",
        ...     "credentials": [
        ...         {"password": "alice.pwd"},
        ...         {"password": "bob.pwd"},
        ...     ]
        ... }
        >>> merge_key_value(data1, data2)
        {
            "key1": "value1",
            "key2": "value2",
            "credentials": [
                {
                    "username": "alice",
                    "password": "alice.pwd",
                },
                {
                    "username": "bob",
                    "password": "bob.pwd",
                },
            ],
        }
    """
    data1 = copy.deepcopy(data1)
    data2 = copy.deepcopy(data2)
    if _fullpath is None:
        _fullpath = ""

    difference = data2.keys() - data1.keys()  # extra keys
    intersection = data1.keys() & data2.keys()  # common keys

    # for extra keys, just add them to data1
    for key in difference:
        data1[key] = data2[key]

    for key in intersection:
        value1, value2 = data1[key], data2[key]
        # if both values are dict, merge them recursively
        if isinstance(value1, dict) and isinstance(value2, dict):
            data1[key] = merge_key_value(value1, value2, f"{_fullpath}.{key}")
        # if both values are list of dict, and has the same size, merge them recursively
        elif isinstance(value1, list) and isinstance(value2, list):
            if len(value1) != len(value2):
                raise ValueError(f"list length mismatch: path = '{_fullpath}.{key}'")
            value = list()
            for item1, item2 in zip(value1, value2):
                if isinstance(item1, dict) and isinstance(item2, dict):
                    value.append(merge_key_value(item1, item2, f"{_fullpath}.{key}"))
                else:
                    raise TypeError(
                        f"items in '{_fullpath}.{key}' are not dict, so you cannot merge them!"
                    )
            data1[key] = value
        else:
            raise TypeError(
                f"type of value at '{_fullpath}.{key}' in data1 and data2 "
                f"has to be both dict or list of dict to merge! "
                f"they are {type(value1)} and {type(value2)}."
            )

    return data1
