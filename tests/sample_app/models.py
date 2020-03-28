from django.db import models
from django.contrib.auth.models import User


class Address(models.Model):

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="address", null=True, blank=True
    )
    tags = models.ManyToManyField("Tag", related_name="addresses", blank=True)

    state = models.CharField(max_length=2)
    zip_code = models.CharField(max_length=12)


class Client(models.Model):

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="client", null=False, blank=False
    )


class Tag(models.Model):

    name = models.CharField(max_length=12, null=False, blank=False,)
