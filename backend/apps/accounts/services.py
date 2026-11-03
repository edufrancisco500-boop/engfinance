import hashlib
from datetime import timedelta
from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from .models import LoginThrottle


@transaction.atomic
def local_authenticate(request, username, password):
    now = timezone.now()
    username = username[:254]
    identities = [
        ("user:" + username.casefold(), 5),
        ("ip:" + request.META.get("REMOTE_ADDR", "unknown"), 30),
    ]
    records = []
    for identity, limit in sorted(identities):
        key = hashlib.sha256(identity.encode()).hexdigest()
        LoginThrottle.objects.get_or_create(key=key, defaults={"window_start": now})
        record = LoginThrottle.objects.select_for_update().get(key=key)
        if now - record.window_start > timedelta(minutes=15):
            record.window_start = now
            record.failures = 0
            record.save()
        records.append((record, limit))
    if any(record.failures >= limit for record, limit in records):
        return None, True
    user = authenticate(request, username=username, password=password)
    for record, _ in records:
        record.failures = (
            0
            if user
            and record.key
            == hashlib.sha256(("user:" + username.casefold()).encode()).hexdigest()
            else record.failures + (0 if user else 1)
        )
        record.save(update_fields=["failures"])
    return user, False
