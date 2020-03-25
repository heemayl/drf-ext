"""Serializer metaclasses that are used for enhancing
functionalities of serializers.
"""

# mypy: ignore-errors

import copy

from collections.abc import Mapping
from typing import Dict, List, Tuple, Any, TypeVar, Optional, Set, Iterable

from rest_framework.serializers import (
    SerializerMetaclass,
    BaseSerializer,
    ModelSerializer,
    ALL_FIELDS,
    IntegerField,
)
from rest_framework.exceptions import ValidationError

from .mixins import NestedCreateUpdateMixin
from .utils import update_error_dict, logger


__all__ = [
    "NestedCreateUpdateMetaclass",
    "FieldOptionsMetaclass",
    "ExtendedSerializerMetaclass",
    "InheritableExtendedSerializerMetaclass",
]


NON_FIELD_ERRORS_KEY = "__all__"


# Custom type hints
SerializerInstance = TypeVar("SerializerInstance")  # refers to a serializer instance


def _get_meta_fields(cls_name: str, cls_attrs: Dict[str, Any]) -> Iterable:
    """Return the fields defined in the `fields` attribute
    of `Meta` class in the serializer.
    """

    try:
        Meta = cls_attrs["Meta"]
    except KeyError:
        raise ValueError(f"No `Meta` class defined on {cls_name}.") from None

    try:
        meta_fields = Meta.fields
    except AttributeError:
        raise ValueError(
            f'No "fields" defined on `Meta` class of {cls_name}.'
        ) from None

    return meta_fields


class NestedCreateUpdateMetaclass(SerializerMetaclass):
    """Metaclass to:
    - transparently add `_pk` field to all nested serializers
    - provide writing capabilities for nested serializers, both while
      creating and updating (via transparently adding the `NestedCreateUpdateMixin`
      into the bases of the created serializer class).
    """

    def __new__(
        metacls: type, cls_name: str, bases: Tuple, attrs: Dict[str, Any]
    ) -> "NestedCreateUpdateMetaclass":

        _get_meta_fields(cls_name, attrs)

        # Inject `_pk` field to all nested serializers
        for attr, value in attrs.items():
            if isinstance(value, BaseSerializer):

                if not isinstance(value, ModelSerializer):
                    logger.info(
                        f"{value} is a `BaseSerializer` instance but not a "
                        "`ModelSerializer`, not going to add `_pk` field here."
                    )
                    continue

                # Keep the declared serializer as-is; work on a copy and
                # set the new one as the serializer eventually
                serializer = copy.deepcopy(value)
                serializer.__class__._declared_fields.update(
                    _pk=IntegerField(
                        write_only=True,
                        required=False,
                        min_value=0,
                        help_text=(
                            "This *write-only* field is used for differentiating "
                            "between `create` and `update` operations of nested "
                            "serializers. And must refer to a valid primary key "
                            "for the relevant nested serializer model to indicate "
                            "that the operation on nested serializer is an `update` "
                            "of the object referred by the given primary key. "
                            "Otherwise, a `create` operation is performed."
                        ),
                    )
                )

                serializer_meta_fields = serializer.Meta.fields

                # When `Meta.fields` is `__all__`, the `_pk` field
                # is added via `get_default_field_names` method
                if serializer_meta_fields == ALL_FIELDS:
                    get_default_field_names_orig = serializer.get_default_field_names

                    def get_default_field_names(*args, **kwargs):
                        default_fields = get_default_field_names_orig(*args, **kwargs)
                        return default_fields + ["_pk"]

                    serializer.get_default_field_names = get_default_field_names
                else:
                    serializer.__class__.Meta.fields = tuple(serializer_meta_fields) + (
                        "_pk",
                    )

                attrs[attr] = serializer

        # `NestedCreateUpdateMixin` should be the first superclass
        bases = (NestedCreateUpdateMixin,) + bases

        return super().__new__(metacls, cls_name, bases, attrs)  # type: ignore


class FieldOptionsMetaclass(SerializerMetaclass):
    """Custom Serializer Metaclass to:
    - provide two `Meta` options to do `required` field validations:
      - `required_fields_on_create`
      - `required_fields_on_update`
    - provide two `Meta` options to do an OR-ed `required` field validations:
      - `required_fields_on_create_any`
      - `required_fields_on_update_any`
      The difference of these with the `required_fields_on_create` and
      `required_fields_on_update` versions is that, in this the existence
      of "any" one of the mentioned fields would suffice.
    *NOTE:* Same field can't be used in both `*_any` and non-any version
      for `create` and `update`.
    - provide `non_required_fields` (iterable) attribute on `Meta` to
      make certain fields as `required=False`. If no `non_required_fields`
      is present on `Meta`, this defaults to `Meta.fields` (given
      `Meta.fields` is an iterable, not string `__all__` [`ALL_FIELDS`]).
      So in that case, all fields declared in `Meta.fields` are marked as
      `required=False`.
    - provide `common_field_params` attribute on `Meta` to add some common
      parameters to a set of fields. This must be a `dict` with the keys
      being an (hashable) iterable e.g. `tuple` and values being a `dict`
      of parameter-values. For example:
          class MySerializer(Serializer):
              ...
              class Meta:
                  ...
                  common_field_params = {
                      ('field_1', 'field_2', 'field_3'): {
                          'write_only' True,
                          'allow_blank: False,
                      },
                  }

    """

    def __new__(
        metacls: type, cls_name: str, bases: Tuple, attrs: Dict[str, Any]
    ) -> "ExtendedSerializerMetaclass":

        cls = super().__new__(metacls, cls_name, bases, attrs)

        Meta = attrs["Meta"]

        required_fields_on_create = required_fields_on_update = ()
        required_fields_on_create_any = required_fields_on_update_any = ()

        # This will be used to check the existence of defined
        # `Meta.non_required_fields` and `Meta.common_field_params`
        # in `Meta.fields` before setting
        meta_fields_set = set(Meta.fields) if Meta.fields != ALL_FIELDS else set()

        try:
            extra_kwargs = Meta.extra_kwargs
        except AttributeError:
            extra_kwargs = Meta.extra_kwargs = {}

        # `non_required_fields`
        try:
            non_required_fields = Meta.non_required_fields
        # Defaults to `fields`
        except AttributeError:
            # TODO: Populate fields when `Meta.fields == '__all__'`
            if Meta.fields == ALL_FIELDS:
                logger.info(
                    "`non_required_fields` is not supported "
                    "currently when `fields == '__all__'`."
                )
                non_required_fields = ()
            else:
                non_required_fields = Meta.fields

        non_required_fields = tuple(non_required_fields) + ("_pk",)
        for field in non_required_fields:
            if field in cls._declared_fields:
                field_obj = cls._declared_fields[field]
                setattr(field_obj, "required", False)
                # `Field` class saves a reference on
                # `_kwargs` and use in `__deepcopy__`
                # (see `fields.Field.__deepcopy__`)
                field_obj._kwargs["required"] = False
            else:
                # For explicitly declared `Meta.fields`, check
                # if the field exists there
                if (Meta.fields == ALL_FIELDS) or (field in meta_fields_set):
                    extra_kwargs.setdefault(field, {}).update(required=False)

        # `common_field_params`
        common_field_params = getattr(Meta, "common_field_params", {})
        if isinstance(common_field_params, Mapping):
            for fields, params_dict in common_field_params.items():
                for field in fields:
                    if field in cls._declared_fields:
                        field_obj = cls._declared_fields[field]
                        for key, value in params_dict.items():
                            setattr(field_obj, key, value)
                            field_obj._kwargs[key] = value
                    else:
                        # For explicitly declared `Meta.fields`, check
                        # if the field exists there
                        if (Meta.fields == ALL_FIELDS) or (field in meta_fields_set):
                            extra_kwargs.setdefault(field, {}).update(params_dict)

        required_fields_on_create = Meta.__dict__.get(
            "required_fields_on_create", required_fields_on_create
        )
        required_fields_on_update = Meta.__dict__.get(
            "required_fields_on_update", required_fields_on_update
        )
        required_fields_on_create_any = Meta.__dict__.get(
            "required_fields_on_create_any", required_fields_on_create_any
        )
        required_fields_on_update_any = Meta.__dict__.get(
            "required_fields_on_update_any", required_fields_on_update_any
        )

        common_create_fields: Set[Any] = set(required_fields_on_create) & set(
            required_fields_on_create_any
        )
        if common_create_fields:
            raise ValueError(
                f'"{", ".join(common_create_fields)}" set inside '
                "both Meta.required_fields_on_create and "
                "Meta.required_fields_on_create_any"
            )

        common_update_fields: Set[Any] = set(required_fields_on_update) & set(
            required_fields_on_update_any
        )
        if common_update_fields:
            raise ValueError(
                f'"{", ".join(common_update_fields)}" set inside '
                "both Meta.required_fields_on_update and "
                "Meta.required_fields_on_update_any"
            )

        # Keep a reference to the original `is_valid` method
        is_valid_orig = getattr(cls, "is_valid", None)

        def is_valid(obj, raise_exception: bool = False) -> Optional[bool]:
            """Custom `is_valid` method to perform the
            `required_fields_*` checks for create and
            update operations.
            """

            if hasattr(obj, "initial_data"):
                if isinstance(obj.initial_data, Mapping):
                    data = obj.initial_data

                    errors: Dict[str, List] = {}

                    if obj.instance or "_pk" in data:
                        required_fields = required_fields_on_update
                        required_fields_any = required_fields_on_update_any
                    else:
                        required_fields = required_fields_on_create
                        required_fields_any = required_fields_on_create_any

                    # `required_fields_on_create`/`required_fields_on_update`
                    for field in required_fields:
                        if field not in data:
                            update_error_dict(errors, field, "This field is required.")

                    # `required_fields_on_create_any`/`required_fields_on_update_any`
                    if required_fields_any:
                        for field in required_fields_any:
                            if field in data:
                                break
                        else:
                            update_error_dict(
                                errors,
                                NON_FIELD_ERRORS_KEY,
                                (
                                    f'At least one of "{", ".join(required_fields_any)}" '
                                    "is required."
                                ),
                            )

                    if errors:
                        if raise_exception:
                            raise ValidationError(errors)
                        return False

            return is_valid_orig(obj, raise_exception=raise_exception)

        cls.is_valid = is_valid

        return cls


class ExtendedSerializerMetaclass(NestedCreateUpdateMetaclass, FieldOptionsMetaclass):
    """Custom SerializerMetaclass to combine the functionalities
    provided by the `NestedCreateUpdateMetaclass` and
    `FieldOptionsMetaclass` metaclasses.

    See the docstrings of those metaclasses.
    """

    pass


class InheritableExtendedSerializerMetaclass(ExtendedSerializerMetaclass):
    """Custom metaclass to include all the attributes
    defined in superclasses (ignoring the dunder and
    `Meta` attributes, and callables).

    This is designed to be used instead of `ExtendedSerializerMetaclass`
    when a (common) base class contains field definitions
    that are to be inherited by all child classes. For example:

    class Common:
        field = serializers.IntegerField()

    class Serializer(
        serializers.ModelSerializer,
        metaclass=InheritableExtendedSerializerMetaclass
    ):
        # `field` will be injected here like it were defined
        # on this class body.
        ...
    """

    def __new__(metacls, cls_name, bases, attrs):

        # Earlier superclasses in the inheritence chain
        # take precedence
        _bases = reversed(bases)

        bases_attrs = {
            attr: value
            for base in _bases
            for attr, value in base.__dict__.items()
            if (not attr.startswith("__"))
            and (attr != "Meta")
            and (not callable(value))
        }

        attrs = {**bases_attrs, **attrs}

        return super().__new__(metacls, cls_name, bases, attrs)
