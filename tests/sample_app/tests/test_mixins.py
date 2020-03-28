"""Test all mixins."""

import pytest

from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from drf_ext.mixins import NestedCreateUpdateMixin
from drf_ext.utils import exc_dict_has_keys

from sample_app.models import Address, Client
from .factories import UserFactory, ClientFactory


class AddressSerializer(serializers.ModelSerializer):

    _pk = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Address
        fields = ("pk", "_pk", "state", "zip_code", "tags")
        read_only_fields = ("pk",)


class UserSerializer(NestedCreateUpdateMixin, serializers.ModelSerializer):
    address = AddressSerializer()
    _pk = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ("pk", "_pk", "username", "password", "address")
        read_only_fields = ("pk",)
        extra_kwargs = {
            "username": {"required": False},
            "password": {"required": False},
        }


class ClientSerializer(NestedCreateUpdateMixin, serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Client
        fields = ("pk", "user")


class TestNestedCreateUpdateMixin:
    def test_depth_1_nested_serializer_valid_data_on_create(self, db):
        address_data = dict(state="CA", zip_code="12345")
        user_data = dict(username="username", password="password")
        user_data.update(address=address_data)

        serializer = UserSerializer(data=user_data)
        assert serializer.is_valid(raise_exception=True)
        user = serializer.save()
        assert user.username == user_data["username"]
        assert user.address.zip_code == address_data["zip_code"]

    def test_depth_1_nested_serializer_valid_data_on_create_with_m2m_field(self, tags):
        tags_pk = [tag.pk for tag in tags]
        address_data = dict(state="CA", zip_code="12345", tags=tags_pk)
        user_data = dict(username="username", password="password")
        user_data.update(address=address_data)

        serializer = UserSerializer(data=user_data)
        assert serializer.is_valid(raise_exception=True)
        user = serializer.save()
        assert [*user.address.tags.all()] == tags

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

    def test_depth_2_nested_serializer_valid_data_on_create_with_m2m_field(self, tags):
        tags = tags[:3]
        tags_pk = [tag.pk for tag in tags]
        address_data = dict(state="CA", zip_code="12345", tags=tags_pk)
        user_data = dict(username="username", password="password")
        user_data.update(address=address_data)
        client_data = dict(user=user_data)

        serializer = ClientSerializer(data=client_data)
        assert serializer.is_valid(raise_exception=True)
        client = serializer.save()
        assert [*client.user.address.tags.all()] == tags

    def test_depth_1_nested_serializer_invalid_data_on_create(self, db):
        address_data = dict(state="CA", zip_code="12345")
        user_data = dict(username="username", password="password")
        user_data.update(address=address_data)

        serializer = UserSerializer(data=user_data)
        assert serializer.is_valid(raise_exception=True)

        serializer.validated_data["address"].pop("zip_code")  # remove `zip_code`
        with pytest.raises(ValidationError) as exc_info:
            serializer.save()
        assert exc_dict_has_keys(exc_info.value, "address")

        # Retreive nested error keys
        address_keys = {
            address_key
            for arg in exc_info.value.args
            if isinstance(arg, dict)
            for value in arg.values()
            if isinstance(value, dict)
            for address_key in value
        }
        assert "zip_code" in address_keys

    def test_depth_2_nested_serializer_invalid_data_on_create(self, db):
        address_data = dict(state="CA", zip_code="12345")
        user_data = dict(username="username", password="123456")
        user_data.update(address=address_data)
        client_data = dict(user=user_data)

        serializer = ClientSerializer(data=client_data)
        assert serializer.is_valid(raise_exception=True)

        serializer.validated_data["user"]["address"].pop(
            "zip_code"
        )  # remove `zip_code`
        with pytest.raises(ValidationError) as exc_info:
            serializer.save()
        assert exc_dict_has_keys(exc_info.value, "user")

        user_keys = {
            user_key
            for arg in exc_info.value.args
            if isinstance(arg, dict)
            for value in arg.values()
            if isinstance(value, dict)
            for user_key in value
        }
        assert "address" in user_keys

        address_keys = {
            inner_key
            for arg in exc_info.value.args
            if isinstance(arg, dict)
            for user_value in arg.values()
            if isinstance(user_value, dict)
            for address_value in user_value.values()
            if isinstance(address_value, dict)
            for inner_key in address_value
        }
        assert "zip_code" in address_keys

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

    def test_depth_1_nested_serializer_invalid_data_on_update(self, db):
        user = UserFactory.create()
        address_pk = user.address.pk

        address_data = dict(_pk=address_pk, state="CA", zip_code="12345")
        user_data = dict(email="user@example.com", password="123456")
        user_data.update(address=address_data)

        serializer = UserSerializer(user, data=user_data)
        assert serializer.is_valid(raise_exception=True)

        serializer.validated_data["address"].pop("zip_code")
        with pytest.raises(ValidationError) as exc_info:
            serializer.save()
        assert exc_dict_has_keys(exc_info.value, "address")

        address_keys = {
            address_key
            for arg in exc_info.value.args
            if isinstance(arg, dict)
            for value in arg.values()
            if isinstance(value, dict)
            for address_key in value
        }
        assert "zip_code" in address_keys

    def test_depth_2_nested_serializer_invalid_data_on_update(self, db):
        client = ClientFactory.create()
        user_pk = client.user.pk
        address_pk = client.user.address.pk

        address_data = dict(_pk=address_pk, state="CA", zip_code="12345")
        user_data = dict(_pk=user_pk, email="user@example.com", password="123456")
        user_data.update(address=address_data)
        client_data = dict(user=user_data)

        serializer = ClientSerializer(client, data=client_data)
        assert serializer.is_valid(raise_exception=True)

        serializer.validated_data["user"]["address"].pop("zip_code")
        with pytest.raises(ValidationError) as exc_info:
            serializer.save()
        assert exc_dict_has_keys(exc_info.value, "user")

        user_keys = {
            user_key
            for arg in exc_info.value.args
            if isinstance(arg, dict)
            for value in arg.values()
            if isinstance(value, dict)
            for user_key in value
        }
        assert "address" in user_keys

        address_keys = {
            inner_key
            for arg in exc_info.value.args
            if isinstance(arg, dict)
            for user_value in arg.values()
            if isinstance(user_value, dict)
            for address_value in user_value.values()
            if isinstance(address_value, dict)
            for inner_key in address_value
        }
        assert "zip_code" in address_keys

    def test_create_nested_object_when_does_not_exist(self, db):
        user = UserFactory.create()
        user.address = None
        user.save()

        address_data = dict(state="CA", zip_code="12345")
        user_data = dict(address=address_data)

        serializer = UserSerializer(user, data=user_data)
        assert serializer.is_valid(raise_exception=True)
        user = serializer.save()

        assert user.address.state == address_data["state"]
        assert user.address.zip_code == address_data["zip_code"]

    def test_create_nested_object_when_exists(self, db):
        user = UserFactory.create()

        address_data = dict(state="CA", zip_code="12345")
        user_data = dict(address=address_data)

        serializer = UserSerializer(user, data=user_data)
        assert serializer.is_valid(raise_exception=True)

        with pytest.raises(ValidationError) as exc_info:
            serializer.save()
        assert exc_dict_has_keys(exc_info.value, "address")
