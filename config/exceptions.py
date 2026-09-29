"""Shared exception types and the DRF exception handler.

Services raise ``ServiceError`` (or a subclass); the handler turns it into a
consistent JSON error body: ``{"detail": "...", "code": "..."}``.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


class ServiceError(Exception):
    """Base class for business-rule violations raised by service layers."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "invalid"

    def __init__(self, message, *, code=None, status_code=None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class NotFoundError(ServiceError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class PermissionDeniedError(ServiceError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"


class ConflictError(ServiceError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


def api_exception_handler(exc, context):
    """Map service/Django errors to JSON responses, else defer to DRF."""
    if isinstance(exc, ServiceError):
        return Response(
            {"detail": exc.message, "code": exc.code}, status=exc.status_code
        )
    if isinstance(exc, DjangoValidationError):
        return Response(
            {"detail": exc.messages, "code": "invalid"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return exception_handler(exc, context)
