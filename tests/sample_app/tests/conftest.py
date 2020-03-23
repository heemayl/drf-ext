"""Pytest fixtures and relevant stuffs."""

from typing import Dict, Any, Iterable

import pytest

from django.contrib.auth.models import User
from rest_framework import serializers

from drf_ext import ExtendedSerializerMetaclass

from sample_app.models import Address, Client

from .factories import AddressFactory, UserFactory, ClientFactory, TagFactory


# Attrbutes to ignore from `<obj>.__dict__` (created by
# `ModelFactory.build()`) when a new instance data is
# generated for POST/PUT/PATCH
_IGNORED_ATTRS_FROM_FACTORY = {
    "address": {"_state", "id"},
    "user": {
        "_state",
        "id",
        "last_login",
        "is_superuser",
        "address_id",
        "is_active",
        "is_staff",
        "date_joined",
    },
    "client": {"_state", "id", "user_id"},
    "tag": {"_state", "id"},
}


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
def get_address_serializer():
    """Return `AddressSerializer` class with the default
    `Meta` attributes updated with the input `meta_attrs`.
    """

    def _get_address_serializer(**meta_attrs):
        class AddressSerializer(
            serializers.ModelSerializer, metaclass=ExtendedSerializerMetaclass
        ):
            class Meta:
                model = Address
                fields = ("pk", "state", "zip_code")
                read_only_fields = ("pk",)

            for attr_name, attr_value in meta_attrs.items():
                setattr(Meta, attr_name, attr_value)

        return AddressSerializer()

    return _get_address_serializer


@pytest.fixture(scope="function")
def get_user_serializer():
    """Return `UserSerializer` class with the default
    `Meta` attributes updated with the input `meta_attrs`.
    """

    def _get_address_serializer(**meta_attrs):
        class UserSerializer(
            serializers.ModelSerializer, metaclass=ExtendedSerializerMetaclass
        ):

            address = get_address_serializer()()

            class Meta:
                model = User
                fields = ("pk", "username", "password", "address")
                read_only_fields = ("pk",)
                extra_kwargs = {
                    "password": {"write_only": True, "trim_whitespace": False}
                }

            for attr_name, attr_value in meta_attrs.items():
                setattr(Meta, attr_name, attr_value)

        return UserSerializer()

    return _get_address_serializer


@pytest.fixture(scope="function")
def get_client_serializer():
    """Return `ClientSerializer` class with the default
    `Meta` attributes updated with the input `meta_attrs`.
    """

    def _get_client_serializer(**meta_attrs):
        class ClientSerializer(
            serializers.ModelSerializer, metaclass=ExtendedSerializerMetaclass
        ):

            user = get_user_serializer()()

            class Meta:
                model = Client
                fields = ("pk", "user")
                read_only_fields = ("pk",)

            for attr_name, attr_value in meta_attrs.items():
                setattr(Meta, attr_name, attr_value)

        return ClientSerializer()

    return _get_client_serializer


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


@pytest.fixture(scope="function")
def client_data_without_tags():

    address = AddressFactory.build()
    user = UserFactory.build()
    client = ClientFactory.build()

    address_data = _get_filtered_dict(
        vars(address), _IGNORED_ATTRS_FROM_FACTORY["address"], include=False
    )
    user_data = _get_filtered_dict(
        vars(user), _IGNORED_ATTRS_FROM_FACTORY["user"], include=False
    )
    client_data = _get_filtered_dict(
        vars(client), _IGNORED_ATTRS_FROM_FACTORY["client"], include=False
    )

    user_data.update(address=address_data)
    client_data.update(user=user_data)

    return client_data


@pytest.fixture(scope="function")
def client_data_with_tags(tags):

    address = AddressFactory.build()
    user = UserFactory.build()
    client = ClientFactory.build()

    address_data = _get_filtered_dict(
        vars(address), _IGNORED_ATTRS_FROM_FACTORY["address"], include=False
    )
    user_data = _get_filtered_dict(
        vars(user), _IGNORED_ATTRS_FROM_FACTORY["user"], include=False
    )
    client_data = _get_filtered_dict(
        vars(client), _IGNORED_ATTRS_FROM_FACTORY["client"], include=False
    )

    user_data.update(address=address_data)
    client_data.update(user=user_data)

    tag_pks = [tag.pk for tag in tags]
    client_data.update(tags=tag_pks)

    return client_data
