"""Tests for stuffs inside drf_ext.utils"""

import pytest

from django.core.exceptions import ValidationError as django_ValidationError
from rest_framework.exceptions import ValidationError

from drf_ext.utils import (
    update_error_dict,
    exc_dict_has_keys,
    get_request_user_on_serializer,
)


def test_update_error_dict():
    errors = {"foo": []}

    update_error_dict(errors, "foo", "Error spamegg")
    assert errors["foo"] == ["Error spamegg"]

    update_error_dict(errors, "bar", "Error spamegg")
    assert errors["bar"] == ["Error spamegg"]

    update_error_dict(errors, "bar", "Error baz")
    assert errors["bar"] == ["Error spamegg", "Error baz"]


def test_exc_dict_has_keys():
    exc_dict = {
        "foo": ["spamegg", "baz"],
        "bar": ["baz"],
    }

    exc = django_ValidationError(exc_dict)
    assert exc_dict_has_keys(exc, "foo")
    assert exc_dict_has_keys(exc, ("foo", "bar"))
    assert not exc_dict_has_keys(exc, "spam")
    assert not exc_dict_has_keys(exc, ("foo", "spam"))

    exc = ValidationError(exc_dict)
    assert exc_dict_has_keys(exc, "foo")
    assert exc_dict_has_keys(exc, ("foo", "bar"))
    assert not exc_dict_has_keys(exc, "spam")
    assert not exc_dict_has_keys(exc, ("foo", "spam"))


def test_get_request_user_on_serializer():
    class Request:
        def __init__(self):
            self.user = True

    class SerializerWithRequestInContext:
        @property
        def context(self):
            return {
                "request": Request(),
            }

    class SerializerWithNoRequestInContext:
        @property
        def context(self):
            return {}

    serializer_instance = SerializerWithRequestInContext()
    assert get_request_user_on_serializer(serializer_instance)

    serializer_instance = SerializerWithNoRequestInContext()
    with pytest.raises(ValueError):
        get_request_user_on_serializer(serializer_instance)
