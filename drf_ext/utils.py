"""All standalone utilities."""

import logging

from typing import Dict, List, TypeVar, Union, Iterable

from rest_framework.serializers import BaseSerializer


__all__ = [
    "update_error_dict",
    "exc_dict_has_keys",
    "get_request_user_on_serializer",
]


# Default logger for `drf_ext`
logger = logging.getLogger("drf_ext")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)


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


def exc_dict_has_keys(exc: Exception, keys: Union[str, Iterable[str]]) -> bool:
    """Test whether the `exc` dict has keys mentioned
    in `keys` iterable. Returns `True` if all the keys
    are found, otherwise returns `False`.

    The `exc` would usually be `ValidationError`.

    The `exc` instance must contain the `args` (tuple)
    attribute containing the mapping of error key name
    and description (e.g. list) values.

    If `keys` is string, it is converted into an iterable.
    """

    if isinstance(keys, str):
        keys = (keys,)

    args = exc.args
    error_args_keys = {key for arg in args if isinstance(arg, dict) for key in arg}

    missing_keys = [key for key in keys if key not in error_args_keys]

    return not bool(missing_keys)


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
