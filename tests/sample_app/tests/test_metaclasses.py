"""Tests for all metaclasses."""

import pytest

from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.utils import model_meta

from drf_ext.metaclasses import (
    NestedCreateUpdateMetaclass,
    ExtendedSerializerMetaclass,
    InheritableExtendedSerializerMetaclass,
    _get_meta_fields,
)

from drf_ext.mixins import NestedCreateUpdateMixin
from drf_ext.utils import exc_dict_has_keys

from sample_app.models import Address, Client
from .factories import UserFactory, ClientFactory


def test_get_meta_fields_no_Meta_should_get_exc():
    class Serializer:
        pass

    with pytest.raises(ValueError):
        _get_meta_fields("Serializer", vars(Serializer))


def test_get_meta_fields_no_Meta_fields_should_get_exc():
    class Serializer:
        class Meta:
            pass

    with pytest.raises(ValueError):
        _get_meta_fields("Serializer", vars(Serializer))


def test_get_meta_fields_with_Meta_fields_should_return():
    class Serializer:
        class Meta:
            fields = "__all__"

    assert _get_meta_fields("Serializer", vars(Serializer)) == Serializer.Meta.fields


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = "__all__"


class UserSerializer(
    serializers.ModelSerializer, metaclass=NestedCreateUpdateMetaclass
):
    address = AddressSerializer()

    class Meta:
        model = User
        fields = "__all__"
        extra_kwargs = {
            "username": {"required": False},
            "password": {"required": False},
        }


class ClientSerializer(
    serializers.ModelSerializer, metaclass=NestedCreateUpdateMetaclass
):
    user = UserSerializer()

    class Meta:
        model = Client
        fields = ("user",)


class TestNestedCreateUpdateMetaclass:
    def test_for_declared_serializer_copying(self):
        class AddressSerializer(serializers.ModelSerializer):
            class Meta:
                model = Address
                fields = "__all__"

        class UserSerializer(
            serializers.ModelSerializer, metaclass=NestedCreateUpdateMetaclass
        ):
            address = AddressSerializer()

            class Meta:
                model = User
                fields = "__all__"

        assert UserSerializer._declared_fields["address"] is not AddressSerializer()

    def test__declared_fields_contains__pk(self):
        class AddressSerializer(serializers.ModelSerializer):
            class Meta:
                model = Address
                fields = "__all__"

        class UserSerializer(
            serializers.ModelSerializer, metaclass=NestedCreateUpdateMetaclass
        ):
            address = AddressSerializer()

            class Meta:
                model = User
                fields = "__all__"

        assert (
            "_pk"
            in UserSerializer._declared_fields["address"].__class__._declared_fields
        )
        assert "_pk" in UserSerializer._declared_fields["address"].fields

    def test_for_nested_serializer_with_fields_as___all__(self):
        class AddressSerializer(serializers.ModelSerializer):
            class Meta:
                model = Address
                fields = "__all__"

        class UserSerializer(
            serializers.ModelSerializer, metaclass=NestedCreateUpdateMetaclass
        ):
            address = AddressSerializer()

            class Meta:
                model = User
                fields = ("address",)

        declared_fields = UserSerializer._declared_fields[
            "address"
        ].__class__._declared_fields
        model_info = model_meta.get_field_info(Address)

        assert "_pk" in UserSerializer._declared_fields[
            "address"
        ].get_default_field_names(declared_fields, model_info)

    def test_for_nested_serializer_with_fields_not_as___all__(self):
        class AddressSerializer(serializers.ModelSerializer):
            class Meta:
                model = Address
                fields = ("state", "zip_code")

        class UserSerializer(
            serializers.ModelSerializer, metaclass=NestedCreateUpdateMetaclass
        ):
            address = AddressSerializer()

            class Meta:
                model = User
                fields = ("address",)

        assert (
            UserSerializer._declared_fields["address"].__class__.Meta.fields
            == AddressSerializer.Meta.fields
        )
        assert (
            UserSerializer._declared_fields["address"].Meta.fields
            == AddressSerializer.Meta.fields
        )
        assert "_pk" in UserSerializer._declared_fields["address"].Meta.fields
        assert "_pk" in AddressSerializer().fields

    def test_depth_1_nested_serializer_valid_data_on_create(self, db):
        address_data = dict(state="CA", zip_code="12345")
        user_data = dict(username="username", password="password")
        user_data.update(address=address_data)

        serializer = UserSerializer(data=user_data)
        assert serializer.is_valid(raise_exception=True)
        user = serializer.save()
        assert user.username == user_data["username"]
        assert user.address.zip_code == address_data["zip_code"]

    def test_depth_2_nested_serializer_valid_data_on_create(self, db):
        address_data = dict(state="CA", zip_code="12345")
        user_data = dict(username="username", password="password")
        user_data.update(address=address_data)
        client_data = dict(user=user_data)

        serializer = ClientSerializer(data=client_data)
        assert serializer.is_valid(raise_exception=True)
        client = serializer.save()
        assert client.user.username == user_data["username"]
        assert client.user.address.zip_code == address_data["zip_code"]

    def test_depth_1_nested_serializer_valid_data_on_update(self, db):
        user = UserFactory.create()
        user.address.state = "CA"
        user.address.zip_code = "12345"
        user.address.save()
        address_pk = user.address.pk

        address_data = dict(_pk=address_pk, state="NJ", zip_code="34567")
        user_data = dict(address=address_data)

        serializer = UserSerializer(user, data=user_data)
        assert serializer.is_valid(raise_exception=True)
        user = serializer.save()
        assert user.address.state == address_data["state"]
        assert user.address.zip_code == address_data["zip_code"]

    def test_depth_2_nested_serializer_valid_data_on_update(self, db):
        client = ClientFactory.create()
        user = client.user
        user.username = "foobar"
        user.save()
        user.address.state = "CA"
        user.address.zip_code = "12345"
        user.address.save()
        user_pk = user.pk
        address_pk = user.address.pk

        address_data = dict(_pk=address_pk, state="NJ", zip_code="34567")
        user_data = dict(_pk=user_pk, username="spamegg", address=address_data)
        requester_data = dict(user=user_data)

        serializer = ClientSerializer(client, data=requester_data)
        assert serializer.is_valid(raise_exception=True)
        client = serializer.save()
        user = client.user

        assert user.username == user_data["username"]
        assert user.address.state == address_data["state"]
        assert user.address.zip_code == address_data["zip_code"]
