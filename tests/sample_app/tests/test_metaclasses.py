"""Tests for all metaclasses."""

import pytest

from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.utils import model_meta

from drf_ext.metaclasses import (
    NestedCreateUpdateMetaclass,
    FieldOptionsMetaclass,
    ExtendedSerializerMetaclass,
    InheritableExtendedSerializerMetaclass,
    _get_meta_fields,
    NON_FIELD_ERRORS_KEY,
)

from drf_ext.mixins import NestedCreateUpdateMixin
from drf_ext.utils import exc_dict_has_keys

from sample_app.models import Address, Client
from .factories import AddressFactory, UserFactory, ClientFactory


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


class TestFieldOptionsMetaclass:
    def test_same_required_field_in_create_and_create_any(self):
        with pytest.raises(ValueError) as exc_info:

            class AddressSerializer(
                serializers.ModelSerializer, metaclass=FieldOptionsMetaclass
            ):
                class Meta:
                    model = Address
                    fields = ("pk", "state", "zip_code")
                    read_only_fields = ("pk",)

                    required_fields_on_create = ("zip_code",)
                    required_fields_on_create_any = ("zip_code", "state")

        assert "zip_code" in exc_info.value.args[0]

    def test_required_fields_on_create(self):
        class AddressSerializer(
            serializers.ModelSerializer, metaclass=FieldOptionsMetaclass
        ):
            class Meta:
                model = Address
                fields = ("pk", "state", "zip_code")
                read_only_fields = ("pk",)

                required_fields_on_create = ("zip_code",)

        data = dict(state="CA", zip_code="12345")
        serializer = AddressSerializer(data=data)
        assert serializer.is_valid(raise_exception=False)

        data.pop("zip_code")
        serializer = AddressSerializer(data=data)
        with pytest.raises(ValidationError) as exc_info:
            serializer.is_valid(raise_exception=True)
        assert exc_dict_has_keys(exc_info.value, "zip_code")

    def test_required_fields_on_create_any(self):
        class AddressSerializer(
            serializers.ModelSerializer, metaclass=FieldOptionsMetaclass
        ):
            class Meta:
                model = Address
                fields = ("pk", "state", "zip_code")
                read_only_fields = ("pk",)

                required_fields_on_create_any = (
                    "state",
                    "zip_code",
                )

        serializer = AddressSerializer(data={})
        with pytest.raises(ValidationError) as exc_info:
            serializer.is_valid(raise_exception=True)
        assert exc_dict_has_keys(exc_info.value, NON_FIELD_ERRORS_KEY)

        serializer = AddressSerializer(data={"state": "CA"})
        assert serializer.is_valid(raise_exception=False)

    def test_same_required_field_in_update_and_update_any(self):
        with pytest.raises(ValueError) as exc_info:

            class AddressSerializer(
                serializers.ModelSerializer, metaclass=FieldOptionsMetaclass
            ):
                class Meta:
                    model = Address
                    fields = ("pk", "state", "zip_code")
                    read_only_fields = ("pk",)

                    required_fields_on_update = ("state",)
                    required_fields_on_update_any = ("zip_code", "state")

        assert "update" in exc_info.value.args[0]

    def test_required_fields_on_update(self, db):
        class AddressSerializer(
            serializers.ModelSerializer, metaclass=FieldOptionsMetaclass
        ):
            class Meta:
                model = Address
                fields = ("pk", "state", "zip_code")
                read_only_fields = ("pk",)

                required_fields_on_update = ("state",)

        instance = AddressFactory.create()
        data = dict(state="CA", zip_code="12345")
        serializer = AddressSerializer(instance, data=data)
        assert serializer.is_valid(raise_exception=False)

        data.pop("state")
        serializer = AddressSerializer(instance, data=data)
        with pytest.raises(ValidationError) as exc_info:
            serializer.is_valid(raise_exception=True)
        assert exc_dict_has_keys(exc_info.value, "state")

    def test_required_fields_on_update_any(self, db):
        class AddressSerializer(
            serializers.ModelSerializer, metaclass=FieldOptionsMetaclass
        ):
            class Meta:
                model = Address
                fields = ("pk", "state", "zip_code")
                read_only_fields = ("pk",)

                required_fields_on_update_any = ("state", "zip_code")

        instance = AddressFactory.create()
        serializer = AddressSerializer(instance, data={})
        with pytest.raises(ValidationError) as exc_info:
            serializer.is_valid(raise_exception=True)
        assert exc_dict_has_keys(exc_info.value, NON_FIELD_ERRORS_KEY)

        serializer = AddressSerializer(instance, data={"zip_code": "12345"})
        assert serializer.is_valid(raise_exception=False)

    def test_non_required_fields_from_fields_not_eq___all__(self):
        class AddressSerializer(
            serializers.ModelSerializer, metaclass=FieldOptionsMetaclass
        ):
            class Meta:
                model = Address
                fields = ("pk", "state", "zip_code")
                read_only_fields = ("pk",)

        serializer = AddressSerializer(data={})
        assert serializer.is_valid(raise_exception=False)

    def test_non_required_fields_from_fields_eq___all__(self):
        """Currently, `non_required_fields` is not
        supported when `Meta.fields` is `__all__`.
        """

        class AddressSerializer(
            serializers.ModelSerializer, metaclass=FieldOptionsMetaclass
        ):
            class Meta:
                model = Address
                fields = "__all__"
                read_only_fields = ("pk",)

        serializer = AddressSerializer(data={})
        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_non_required_fields_empty(self):
        # Need to use a required field i.e. either an explicitly
        # defined field or a `blank=False` field of model
        class AddressSerializer(
            serializers.ModelSerializer, metaclass=FieldOptionsMetaclass
        ):
            class Meta:
                model = Address
                fields = ("zip_code",)

                non_required_fields = ()

        serializer = AddressSerializer(data={})
        with pytest.raises(ValidationError) as exc_info:
            assert serializer.is_valid(raise_exception=True)
        assert exc_dict_has_keys(exc_info.value, "zip_code")

    def test_common_field_params_for_declared_fields(self):
        class AddressSerializer(
            serializers.ModelSerializer, metaclass=FieldOptionsMetaclass
        ):
            city = serializers.CharField()
            zip_code = serializers.CharField()

            class Meta:
                model = Address
                fields = "__all__"

                common_field_params = {
                    ("city", "zip_code"): {
                        "allow_blank": True,
                        "trim_whitespace": False,
                        "min_length": 10,
                    },
                    ("city",): {"max_length": 50},
                    ("zip_code",): {"max_length": 100},
                }

        declared_fields = AddressSerializer._declared_fields

        assert declared_fields["city"]._kwargs["allow_blank"]
        assert not declared_fields["city"]._kwargs["trim_whitespace"]
        assert declared_fields["city"]._kwargs["min_length"] == 10
        assert declared_fields["city"]._kwargs["max_length"] == 50

        assert declared_fields["zip_code"]._kwargs["allow_blank"]
        assert not declared_fields["zip_code"]._kwargs["trim_whitespace"]
        assert declared_fields["zip_code"]._kwargs["min_length"] == 10
        assert declared_fields["zip_code"]._kwargs["max_length"] == 100

    def test_common_field_params_for_non_declared_fields_and_fields_eq___all__(self):
        class AddressSerializer(
            serializers.ModelSerializer, metaclass=FieldOptionsMetaclass
        ):
            class Meta:
                model = Address
                fields = "__all__"

                common_field_params = {
                    ("state", "zip_code"): {
                        "allow_blank": True,
                        "trim_whitespace": False,
                        "min_length": 10,
                    },
                    ("state",): {"max_length": 50},
                    ("zip_code",): {"max_length": 100},
                }

        extra_kwargs = AddressSerializer.Meta.extra_kwargs

        assert extra_kwargs["state"]["allow_blank"]
        assert not extra_kwargs["state"]["trim_whitespace"]
        assert extra_kwargs["state"]["min_length"] == 10
        assert extra_kwargs["state"]["max_length"] == 50

        assert extra_kwargs["zip_code"]["allow_blank"]
        assert not extra_kwargs["zip_code"]["trim_whitespace"]
        assert extra_kwargs["zip_code"]["min_length"] == 10
        assert extra_kwargs["zip_code"]["max_length"] == 100

    def test_common_field_params_for_non_declared_fields_and_fields_not_eq___all__(
        self,
    ):
        class AddressSerializer(
            serializers.ModelSerializer, metaclass=FieldOptionsMetaclass
        ):
            class Meta:
                model = Address
                fields = ("state",)

                common_field_params = {
                    ("state", "zip_code"): {
                        "allow_blank": True,
                        "trim_whitespace": False,
                        "min_length": 10,
                    },
                    ("state",): {"max_length": 50},
                    ("zip_code",): {"max_length": 100},
                }

        extra_kwargs = AddressSerializer.Meta.extra_kwargs

        assert extra_kwargs["state"]["allow_blank"]
        assert not extra_kwargs["state"]["trim_whitespace"]
        assert extra_kwargs["state"]["min_length"] == 10
        assert extra_kwargs["state"]["max_length"] == 50

        with pytest.raises(KeyError):
            assert extra_kwargs["zip_code"]


