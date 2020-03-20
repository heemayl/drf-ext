"""All standalone utilities."""


from typing import Dict, List, TypeVar

from rest_framework.serializers import BaseSerializer


__all__ = ["update_error_dict", "get_request_user_on_serializer"]


# Custom type hint(s)
# Refers to a model or serializer field
FieldName = TypeVar("FieldName")
# Refers to a `User` (`AUTH_USER_MODEL` or `AnonymousUser`) instance
User = TypeVar("User")


def update_error_dict(
    errors: Dict[str, List], field_name: FieldName, message: str
) -> None:
    """Append the `message` to the list of messages for the
    `field_name` key in the `errors` dict. This is usually
    used for aggregating error messages for ValidationError.

    *NOTE:* The values of the `errors` dict must be lists.

    Args:
        errors (dict): The dict to be updated.
        field_name (str): Model field name for which the error
          message is being appended.
        message (str): The error message

    Returns: None
    """

    errors.setdefault(field_name, []).append(message)
    return None


def get_request_user_on_serializer(serializer_instance: BaseSerializer) -> User:
    """Take a serializer instance and return the current
    requesting `User` instance. The `request` object must
    be present in the serializer context.
    """

    try:
        request = serializer_instance.context["request"]
    except KeyError:
        raise ValueError(
            "Serializer context does not have the current reqeust. "
            "Make sure the dict returned by `<view>.get_serializer_context` "
            "method has the `request`."
        ) from None

    return request.user
