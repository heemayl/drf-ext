"""All model factories."""

from functools import partial

from django.contrib.auth.models import User

import factory
import factory.fuzzy

from sample_app.models import (
    Address,
    Client,
    Tag,
)


__all__ = [
    "AddressFactory",
    "UserFactory",
    "ClientFactory",
    "TagFactory",
]


Faker = partial(factory.Faker, locale="en_US")


US_STATE_CHOICES = [
    ("CA", "California"),
    ("NJ", "New Jersey"),
    ("NM", "New Mexico"),
    ("NY", "New York"),
    ("NC", "North Carolina"),
    ("ND", "North Dakota"),
    ("OH", "Ohio"),
]


class AddressFactory(factory.django.DjangoModelFactory):

    state = factory.fuzzy.FuzzyChoice(US_STATE_CHOICES, getter=lambda row: row[0])
    zip_code = Faker("zipcode")

    @factory.post_generation
    def tags(self, create, extracted, **kwargs):
        if not create:
            return None

        if extracted:
            for tag in extracted:
                self.tags.add(tag)

    class Meta:
        model = Address


class UserFactory(factory.django.DjangoModelFactory):

    username = factory.Sequence(lambda num: f"user_{num}")
    password = Faker("text", max_nb_chars=10)

    address = factory.RelatedFactory(AddressFactory, factory_related_name="user")

    class Meta:
        model = User


class ClientFactory(factory.django.DjangoModelFactory):

    user = factory.SubFactory(UserFactory)

    class Meta:
        model = Client


class TagFactory(factory.django.DjangoModelFactory):

    name = Faker("text", max_nb_chars=12)

    class Meta:
        model = Tag
