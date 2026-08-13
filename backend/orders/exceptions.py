"""A single error shape for the whole API."""

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.views import exception_handler as drf_exception_handler


class ServiceError(APIException):
    """Base class for business-rule failures raised by the services layer."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "VALIDATION_ERROR"

    def __init__(self, message: str, details: dict | None = None, code: str | None = None):
        self.message = message
        self.details = details or {}
        if code:
            self.error_code = code
        super().__init__(detail=message)


class OverpaymentError(ServiceError):
    error_code = "OVERPAYMENT"


class OverRefundError(ServiceError):
    error_code = "OVER_REFUND"


class OrderLockedError(ServiceError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "ORDER_LOCKED"


class OrderHasSettlementsError(ServiceError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"


def _flatten_validation_detail(detail, prefix: str = "") -> tuple[str, dict]:
    """Turn DRF's nested validation structure into one sentence plus a field map."""
    fields: dict[str, list[str]] = {}

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            scalars = [str(item) for item in node if not isinstance(item, (dict, list))]
            if scalars:
                fields.setdefault(path or "non_field_errors", []).extend(scalars)
            for index, item in enumerate(node):
                if isinstance(item, (dict, list)):
                    walk(item, f"{path}[{index}]" if path else f"[{index}]")
        else:
            fields.setdefault(path or "non_field_errors", []).append(str(node))

    walk(detail, prefix)

    if fields:
        first_field, messages = next(iter(fields.items()))
        first = messages[0]
        message = first if first_field == "non_field_errors" else f"{first_field}: {first}"
    else:
        message = "The submitted data was not valid."
    return message, fields


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        # Unhandled exception: let Django produce the 500 so it is logged and
        # reported rather than being quietly reshaped into a tidy envelope.
        return None

    if isinstance(exc, ServiceError):
        code, message, details = exc.error_code, exc.message, exc.details
    elif isinstance(exc, ValidationError):
        code = "VALIDATION_ERROR"
        message, details = _flatten_validation_detail(exc.detail)
        details = {"fields": details}
    elif isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        code = "AUTH_REQUIRED"
        message = "You need to be signed in to do that. Log in and try again."
        details = {}
    elif isinstance(exc, PermissionDenied):
        code = "FORBIDDEN"
        message = "You do not have permission to perform this action."
        details = {}
    elif isinstance(exc, (NotFound, Http404)):
        # get_object_or_404 raises Django's Http404, which DRF turns into a 404
        # response but leaves as the original exception type here.
        code = "NOT_FOUND"
        message = "That record does not exist, or it belongs to another account."
        details = {}
    elif isinstance(exc, MethodNotAllowed):
        code = "METHOD_NOT_ALLOWED"
        message = str(exc.detail)
        details = {}
    elif isinstance(exc, Throttled):
        code = "THROTTLED"
        message = str(exc.detail)
        details = {"retry_after_seconds": exc.wait}
    else:
        code = getattr(exc, "default_code", "ERROR").upper()
        detail = getattr(exc, "detail", None)
        message = str(detail) if detail else "Something went wrong."
        details = {}

    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
