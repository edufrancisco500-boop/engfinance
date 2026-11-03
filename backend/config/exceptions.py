from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    if isinstance(exc, IntegrityError):
        return Response(
            {
                "detail": "Registro duplicado ou operação incompatível com a integridade dos dados."
            },
            status=409,
        )
    if isinstance(exc, DjangoValidationError):
        return Response(
            {
                "detail": exc.message_dict
                if hasattr(exc, "message_dict")
                else exc.messages
            },
            status=400,
        )
    return exception_handler(exc, context)
