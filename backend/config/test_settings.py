import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-not-for-deployment")
from .settings import *

# Apenas testes portáteis de cadastro e autorização; não valida concorrência financeira.
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
