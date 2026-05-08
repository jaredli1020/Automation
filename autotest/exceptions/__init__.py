"""自定义异常"""

from .exceptions import (
    AutoTestBaseException,
    DatabaseException,
    ConnectionException,
    QueryException,
    RecordNotFoundException,
    ValidationException,
    ExternalServiceException,
    HttpRequestException,
    JsonParseException,
)

__all__ = [
    "AutoTestBaseException",
    "DatabaseException",
    "ConnectionException",
    "QueryException",
    "RecordNotFoundException",
    "ValidationException",
    "ExternalServiceException",
    "HttpRequestException",
    "JsonParseException",
]
