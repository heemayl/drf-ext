"""All serializer mixins that can be used to extend the
functionalities of default DRF serializers.
"""

# mypy: ignore-errors

import traceback

from collections.abc import Mapping
from typing import Dict, List, Tuple, Any, Union, TypeVar

from django.core.exceptions import ValidationError as django_ValidationError
from rest_framework.serializers import BaseSerializer
from rest_framework.utils import model_meta
from rest_framework.exceptions import ValidationError


__all__ = ["NestedCreateUpdateMixin"]


# Custom type hints
DatabaseModel = TypeVar("DatabaseModel")  # refers to a model
DatabaseModelInstance = TypeVar("DatabaseModelInstance")  # refers to a model instance
SerializerInstance = TypeVar("SerializerInstance")  # refers to a serializer instance


NON_FIELD_ERRORS_KEY = "__all__"


class NestedCreateUpdateMixin:
    """Mixin to provide writing capabilities for nested
    serializers, while creating and updating. This essentially
    provides the `create` and `update` methods to allow
    for nested operations.

    *NOTE:* It separates the nested create and update operations
    based on the existence of the (write-only) `_pk` field. So
    the `_pk` field *MUST* not be made read-only, otherwise it
    will treat all nested operations as `create`. The `_pk` field
    will be pop-ed out so it's a safe operation.
    """

    @staticmethod
    def _get_nested_validation_error(
        nested_field_name: str, exc: Union[ValidationError, django_ValidationError]
    ) -> Union[ValidationError, django_ValidationError]:
        """Wrap a `ValidationError` from nested serializer with
        the nested field name and return.

        For example, If the `ValidationError` contains the content
        `{"foo": ["bar"]}` and the nested field name is "spam",
        this would create a new `ValidationError` with the content
        `{"spam": {"foo": ["bar"]}}`.
        """

        if not isinstance(exc, (ValidationError, django_ValidationError)):
            raise TypeError(
                f"exc must be of type ValidationError, not {type(exc).__name__}."
            )

        args = exc.args
        error_args = {
            key: value
            for arg in args
            if isinstance(arg, dict)
            for key, value in arg.items()
        }

        nested_field_error = {nested_field_name: error_args}

        return exc.__class__(nested_field_error)

    @staticmethod
    def _handle_single_instance_data(
        related_model: DatabaseModel,
        field_obj: SerializerInstance,
        field_data: Dict[str, Any],
    ) -> Tuple[bool, DatabaseModelInstance]:
        """Take the related model and field data for an instance,
        and return whether the instance is created and the instance
        itself (None in case the `_pk` is passed but the object
        does not exist.

        The valid (nested) input data (and `instance` in case of
        `update` -- depending on the existence and validity of
        `_pk`) are passed to the nested serializer class. Then
        `is_valid` and `save` are called on the serializer instance.
        """

        created = True
        instance = None

        # Existence of `_pk` means the object already exists,
        # so we should only update the instance data
        try:
            _pk = field_data.pop("_pk")
        # No `_pk` key, so create the instance
        except KeyError:
            # "To many" serializers are instantiated transparently
            # as `ListSerializer`, with the `child` attribute
            # pointing to the real serializer
            serializer = field_obj.child if hasattr(field_obj, "child") else field_obj
            serializer_cls = serializer.__class__

            serializer = serializer_cls(data=field_data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
        else:
            created = False
            try:
                instance = related_model._default_manager.get(pk=_pk)
            except related_model.DoesNotExist:
                raise ValidationError(
                    {
                        NON_FIELD_ERRORS_KEY: [
                            f"No such {related_model.__name__} object "
                            f"with primary key {_pk} exists."
                        ]
                    }
                ) from None
            else:
                serializer = field_obj.__class__(instance, data=field_data)
                serializer.is_valid(raise_exception=True)
                instance = serializer.save()

        return created, instance

    def _get_related_field_data(
        self, info: model_meta.RelationInfo, validated_data: Dict[str, Any]
    ) -> Tuple[Dict[str, Union[List[int], int]]]:
        """Return a tuple of two dicts: one for 'to_one` relations
        and one for `to_many` relations. The keys are the field
        names and values are integers (PKs). For example:

        related_to_one_fields_data = {'related_field_1': 7}
        related_to_many_fields_data = {'related_field_2': [2, 3]}

        The instance are created first from the validated field
        data (if needed) to get the PK.
        """

        # Get related field data
        related_to_one_fields_data = {}
        related_to_many_fields_data = {}

        # Track newly created instances so that we can remove
        # them for any error
        # TODO: *NOTE:* Any updated instances can't be rolled back (for now)
        created_instances = set()

        try:
            for field in self._writable_fields:
                field_name = field.source

                if (field_name in validated_data) and (field_name in info.relations):

                    relation_info = info.relations[field_name]
                    related_model = relation_info.related_model

                    field_data = validated_data.pop(field_name)

                    if relation_info.to_many:
                        if isinstance(field, BaseSerializer):
                            for single_field_data in field_data:

                                try:
                                    (
                                        created,
                                        instance,
                                    ) = self._handle_single_instance_data(
                                        related_model, field, single_field_data
                                    )
                                except (ValidationError, django_ValidationError) as e:
                                    # TODO: aggregate all ValidationErrors
                                    # and send at once
                                    raise self._get_nested_validation_error(
                                        field_name, e
                                    )

                                if instance:
                                    if created:
                                        created_instances.add(instance)
                                    related_to_many_fields_data.setdefault(
                                        field_name, []
                                    ).append(instance)

                        else:
                            related_to_many_fields_data[field_name] = field_data
                    else:
                        if isinstance(field, BaseSerializer):

                            try:
                                created, instance = self._handle_single_instance_data(
                                    related_model, field, field_data
                                )
                            except (ValidationError, django_ValidationError) as e:
                                raise self._get_nested_validation_error(field_name, e)

                            if instance:
                                if created:
                                    created_instances.add(instance)
                                related_to_one_fields_data[field_name] = instance
                        else:
                            related_to_one_fields_data[field_name] = field_data
        except Exception:
            for instance in created_instances:
                instance.delete()
            raise

        return related_to_one_fields_data, related_to_many_fields_data

    def create(self, validated_data: Dict[str, Any]) -> DatabaseModelInstance:
        """Overriden `create` method to handle nested serializer
        writes. The existence of `_pk` field on field data means
        an update of the nested instance is desired, otherwise the
        nested instance is created first from the passed data for
        the field.
        """

        ModelClass = self.Meta.model

        info = model_meta.get_field_info(ModelClass)

        # fmt: off
        related_to_one_fields_data, related_to_many_fields_data = (
            self._get_related_field_data(
                info, validated_data
            )
        )
        # fmt: on

        validated_data.update(related_to_one_fields_data)

        try:
            instance = ModelClass._default_manager.create(**validated_data)
        except TypeError:
            tb = traceback.format_exc()
            msg = (
                "Got a `TypeError` when calling `%s.%s.create()`. "
                "This may be because you have a writable field on the "
                "serializer class that is not a valid argument to "
                "`%s.%s.create()`. You may need to make the field "
                "read-only, or override the %s.create() method to handle "
                "this correctly.\nOriginal exception was:\n %s"
                % (
                    ModelClass.__name__,
                    ModelClass._default_manager.name,
                    ModelClass.__name__,
                    ModelClass._default_manager.name,
                    self.__class__.__name__,
                    tb,
                )
            )
            raise TypeError(msg)

        # Save many-to-many relationships after the instance is created.
        for field_name, value in related_to_many_fields_data.items():
            field = getattr(instance, field_name)
            field.set(value)

        return instance

    def update(
        self, instance: DatabaseModelInstance, validated_data: Dict[str, Any]
    ) -> DatabaseModelInstance:
        """Overriden `update` method to handle nested serializer
        writes. The existence of `_pk` field on field data means
        an update of the nested instance is desired, otherwise the
        nested instance is created first from the passed data for
        the field.
        """

        info = model_meta.get_field_info(instance)

        # Check whether the nested field data is correct e.g.
        # user can try to update a nested object they are not
        # related to by providing the `_pk` for that.
        for field_name, field_relation in info.relations.items():

            # TODO: The to-many relation data are passed as-is as they
            # will be "set" (like fresh creation). Look into this later.
            if field_relation.to_many:
                continue

            if field_name in validated_data:
                field_data = validated_data[field_name]

                if not isinstance(field_data, Mapping):
                    continue

                related_obj = getattr(instance, field_name)

                if related_obj:
                    try:
                        field_data_pk = field_data["_pk"]
                    except KeyError:
                        # TODO: Should allow for creating new related object?
                        raise ValidationError(
                            {field_name: [("Related object already exists.")]}
                        )
                    else:
                        if related_obj.pk != field_data_pk:
                            raise ValidationError(
                                {
                                    field_name: [
                                        (
                                            "No such "
                                            f"{related_obj.__class__.__name__} "
                                            "object with primary key "
                                            f"{field_data_pk} exists."
                                        )
                                    ]
                                }
                            )

        # fmt: off
        related_to_one_fields_data, related_to_many_fields_data = (
            self._get_related_field_data(
                info, validated_data
            )
        )
        # fmt: on

        validated_data.update(related_to_one_fields_data)

        for attr_name, value in validated_data.items():
            setattr(instance, attr_name, value)
        instance.save()

        # Note that many-to-many fields are set after updating instance.
        # Setting m2m fields triggers signals which could potentially change
        # updated instance and we do not want it to collide with .update()
        for field_name, value in related_to_many_fields_data.items():
            field = getattr(instance, field_name)
            field.set(value)

        return instance
