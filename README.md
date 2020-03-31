# DRF Ext (Django REST Framework Extensions)

## Extensions for the DRF

# Installation:

	pip install drf-ext

---

# Features/Extensions:

- Nested model serializer saving (`create`/`update`)
- Declaration of non-required fields
- Add multiple common parameters to a set of fields
- Check fields' existence on de-serialization (`create`/`update`)
- Check any field's existence among a set of fields on de-serialization (`create`/`update`)
- Several frequently used utilities

---

# Available objects:

### Metaclasses:

- `NestedCreateUpdateMetaclass`: provides nested serializer writes on `create` and `update`.
- `FieldOptionsMetaclass`: provides various field declaration options for different scenarios.
- `ExtendedSerializerMetaclass`: contains both `NestedCreateUpdateMetaclass` and `FieldOptionsMetaclass`.
- `InheritableExtendedSerializerMetaclass`: `ExtendedSerializerMetaclass` with inheritance support.

### Mixins:

- `NestedCreateUpdateMixin`: provides nested serializer writes on `create` and `update` (used by `NestedCreateUpdateMetaclass`), see example below.


### Utilities:

- `update_error_dict`: allows updating a `ValidationError` error dict with provided key/value.
- `exc_dict_has_keys`: tests whether given key(s) are in the exception error dict (e.g. `ValidationError`).
- `get_request_user_on_serializer`: gets the current user object from inside the serializer.

---

**NOTE:** All of the above are `import`-able from `drf_ext` e.g.:

```python

from drf_ext import NestedCreateUpdateMetaclass, update_error_dict

```

---

# Examples:

Assuming the following `models.py`:

```python

from django.db import models
from django.contrib.auth.models import User


class Tag(models.Model):

	name = models.CharField(max_length=12)


class Address(models.Model):

	user = models.OneToOneField(
		User,
		on_delete=models.CASCADE,
		related_name="address",
		null=True,
		blank=True,
	)
	tags = models.ManyToManyField(Tag, related_name="addresses", blank=True)

	state = models.CharField(max_length=2)
	zip_code = models.CharField(max_length=12)


class Client(models.Model):

	user = models.OneToOneField(
		User,
		on_delete=models.CASCADE,
		related_name="client",
		null=False,
		blank=False,
	)


```

## Metaclasses/mixins:

### `NestedCreateUpdateMetaclass`/`NestedCreateUpdateMixin`:

`serializers.py`:

```python

from rest_framework import serializers

from drf_ext import NestedCreateUpdateMetaclass


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

```

Sample *POST* request:

```python

data = {
	"username": "my_username",
	"password": "my_password",
	"address": {
		"state": "CA",
		"zip_code": "12345",
		"tags": [1, 3, 7]  # `pk` of `Tag` objects
	}
}

client.post("/users/", data=data)

```

Sample *PUT/PATCH* request:

```python

data = {
	"address": {
		"_pk": 2,  # `pk` of the related `address`
		"state": "CA",
		"zip_code": "12345",
		"tags": [9, 24, 56]
	}
}

client.patch("/users/1/", data=data)

```

**NOTE:** `drf_ext` uses the existence of `_pk` field to track
whether it's a new nested object creation or an update. So if
`_pk` is omitted it would taken as new nested object creation
request.

This `_pk` **write-only** field is automatically
injected to all nested serializers by the metaclass. But if
one is using the `NestedCreateUpdateMixin`, they need to
explicitly define the field on the nested serializer e.g.:

```python

class AddressSerializer(serializers.ModelSerializer):

	_pk = serializers.IntegerField(write_only=True, required=False)  # here

	class Meta:
		model = Address
		fields = ("pk", "_pk", "state", "zip_code")
		read_only_fields = ("pk",)


class UserSerializer(NestedCreateUpdateMixin, serializers.ModelSerializer):

	address = AddressSerializer()

	class Meta:
		model = User
		fields = "__all__"

```

Everything else remains the same as `NestedCreateUpdateMetaclass`.


### `FieldOptionsMetaclass`:

#### `required_fields_on_create`, `required_fields_on_update`, `required_fields_on_create_any`, `required_fields_on_update_any`:

```python

class AddressSerializer(serializers.ModelSerializer, metaclass=FieldOptionsMetaclass):
	class Meta:
		model = Address
		fields = ("pk", "state", "zip_code")
		read_only_fields = ("pk",)

		# These fields are required on POST request i.e. on creation of object
		required_fields_on_create = ("state", "zip_code")

		# These fields are required on PUT/PATCH request i.e. on update of object
		required_fields_on_update = ("zip_code",)


class UserSerializer(
	serializers.ModelSerializer, metaclass=FieldOptionsMetaclass
):
	address = AddressSerializer()

	class Meta:
		model = User
		fields = (
			"pk", "address", "username", "email",
			"password", "first_name", "last_name",
		)
		read_only_fields = ("pk",)

		# At least one of these fields are required on POST request
		required_fields_on_create_any = ("first_name", "last_name")

		# At least one of these fields are required on PUT/PATCH request
		required_fields_on_update_any = ("address", "username", "email")

```

#### `non_required_fields`:

```python

class AddressSerializer(serializers.ModelSerializer, metaclass=FieldOptionsMetaclass):
	class Meta:
		model = Address
		fields = ("pk", "state", "zip_code")
		read_only_fields = ("pk",)

		# The mentioned fields are made *non-required*, like providing
		# the `required=False` parameter on them. All fields are taken
		# as required, unless model has `blank=True` on the field, or
		# explicitly mentioned with `required=False`. This will allow
		# to control that from a single place. Also, this would make
		# working with `required_fields_on_create` and related options
		# (see above) easier to follow as users can decide to make a
		# field mandatory in POST but not in PUT/PATCH and vice versa,
		# which allows for a finer control over fields.
		non_required_fields = ("state", "zip_code")

```

**NOTE:** If `non_required_fields` is not provided, all fields mentioned
in `fields` (without `exclude`-ed ones) are made *non-required*. To use
the default option of DRF, one can set `non_required_fields` to an empty
iterable e.g.:

```python

class AddressSerializer(serializers.ModelSerializer, metaclass=FieldOptionsMetaclass):
	class Meta:
		model = Address
		fields = ("pk", "state", "zip_code")

		non_required_fields = ()

```
---

#### `common_field_params`:

```python
class AddressSerializer(serializers.ModelSerializer, metaclass=FieldOptionsMetaclass):
	class Meta:
		model = Address
		fields = ("pk", "state", "zip_code")
		read_only_fields = ("pk",)

		# `common_field_params` allows to add some common parameters
		# to a set of fields. This must be a `dict` with the keys
		# being an (hashable) iterable e.g. `tuple` and values being
		# a `dict` of parameter-values.
		common_field_params = {
			("state", zip_code"): {
				"allow_blank": False,
				"trim_whitespace": True,
			},

			# Using a single field is also fine (this works similar
			# to the default `extra_kwargs` in that case).
			("state",): {
				"max_length": 2,
			},
		}

```

---

### `ExtendedSerializerMetaclass`:

If you want to use all features from `NestedCreateUpdateMetaclass` and
`FieldOptionsMetaclass` mentioned above, use this metaclass:

```python

class UserSerializer(serializers.ModelSerializer, metaclass=ExtendedSerializerMetaclass):

	address = AddressSerializer()

	class Meta:
		model = Address
		fields = "__all__"

		required_fields_on_create = ("username, "password",)
		required_fields_on_update_any = ("first_name", "last_name", "email")

```

Sample *POST* request:

```python

data = {
	"username": "my_username",
	"password": "my_password",
	"address": {
		"state": "CA",
		"zip_code": "12345"
	}
}

client.post("/users/", data=data)

```
---

### `InheritableExtendedSerializerMetaclass`:

Works exactly like `ExtendedSerializerMetaclass`. This one should be
used to include all the attributes defined in superclasses (ignoring
the dunder and `Meta` attributes, and callables).

This is designed to be used instead of `ExtendedSerializerMetaclass`
when e.g. a (common) base class contains field definitions that are
to be inherited by all child classes. For example:

```python

	class Common:
		field = serializers.IntegerField()

	class Serializer(
		serializers.ModelSerializer,
		metaclass=InheritableExtendedSerializerMetaclass
	):
		# `field` will be injected here like it were defined
		# on this class body.
		...

```

---

## Utilities:

### `update_error_dict`:

```python

errors = {}

if ...:
	# Following will result in `errors` being:
	# `{"field": ["Error message"]}`
	update_error_dict(errors, "field", "Error message")

if ...:
	# Following will result in `errors` being:
	# `{"field": ["Error message", "New error message"]}`
	update_error_dict(errors, "field", "New error message")

if errors:
	raise ValidationError(errors)

```

---

### `exc_dict_has_keys`:

```python

exc = ValidationError({
	"field_1": ["msg", "new msg"],
	"field_2": ["msg"],
})

exc_dict_has_keys(exc, ("field_1", "field_2"))  # returns `True`
exc_dict_has_keys(exc, "field_1")  # returns `True`

exc_dict_has_keys(exc, ("field_1", "field_2", "field_3"))  # returns `False`
exc_dict_has_keys(exc, "field_3")  # returns `False`

```

---

### `get_request_user_on_serializer`:

```python

class MySerializer(serializers.Serializer):
	...
	...

	def create(self, validated_data):
		# Get the user sending this request
		user = get_request_user_on_serializer(self)

```

---

# Development:

- Install `dev` dependencies:

		pip install drf-ext[dev]

- Run tests:

		drf_ext/tests$ PYTHONPATH=.. pytest

---

## License:

#### MIT

---
