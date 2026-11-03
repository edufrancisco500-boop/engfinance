from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Identidade extensível antes da primeira migration."""


class LoginThrottle(models.Model):
    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField()
