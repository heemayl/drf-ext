"""Pytest fixtures and relevant stuffs."""

from typing import Dict, Any, Iterable

import pytest

from .factories import ClientFactory, TagFactory


def _get_filtered_dict(
    input_dict: Dict[str, Any], keys_to_consider: Iterable[str], include: bool = False
) -> Dict[str, Any]:
    """Return a new filtered dict from `input_dict`. If
    `include` is `True`, only the keys in `keys_to_consider`
    is returned, otherwise only the keys that are not in
    `keys_to_consider` are returned.
    """

    keys_to_consider = set(keys_to_consider)

    if not keys_to_consider:
        return {}

    if include:
        _check = lambda key: key in keys_to_consider  # noqa
    else:
        _check = lambda key: key not in keys_to_consider  # noqa

    return {key: value for key, value in input_dict.items() if _check(key)}


@pytest.fixture(scope="function")
def client(db):
    return ClientFactory.create()


@pytest.fixture(scope="function")
def clients(db):
    return ClientFactory.create_batch(5)


@pytest.fixture(scope="function")
def tag(db):
    return TagFactory.create()


@pytest.fixture(scope="function")
def tags(db):
    return TagFactory.create_batch(5)
