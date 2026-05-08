"""自定义异常层级

所有框架异常继承自 AutoTestBaseException，统一 code + details 结构，
方便日志记录和 API 响应序列化。
"""


class AutoTestBaseException(Exception):
    """框架基础异常类"""

    def __init__(self, message: str, code: str = None, details: dict = None):
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "error_code": self.code,
            "message": self.message,
            "details": self.details,
        }


class DatabaseException(AutoTestBaseException):
    """数据库相关异常"""

    def __init__(self, message: str, query: str = None, params: tuple = None):
        details = {}
        if query:
            details["query"] = query[:200] + "..." if len(query) > 200 else query
        if params:
            details["params_count"] = len(params)
        super().__init__(message, code="DATABASE_ERROR", details=details)


class ConnectionException(DatabaseException):
    """数据库连接异常"""

    def __init__(self, message: str, database_name: str = None):
        super().__init__(message)
        self.code = "CONNECTION_ERROR"
        if database_name:
            self.details["database"] = database_name


class QueryException(DatabaseException):
    """查询执行异常"""

    def __init__(self, message: str, query: str = None, params: tuple = None):
        super().__init__(message, query, params)
        self.code = "QUERY_ERROR"


class RecordNotFoundException(DatabaseException):
    """记录未找到异常"""

    def __init__(self, message: str, table: str = None, identifier: any = None):
        super().__init__(message)
        self.code = "RECORD_NOT_FOUND"
        if table:
            self.details["table"] = table
        if identifier is not None:
            self.details["identifier"] = str(identifier)


class ValidationException(AutoTestBaseException):
    """参数校验异常"""

    def __init__(self, message: str, field: str = None, value: any = None):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)[:100]
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class ExternalServiceException(AutoTestBaseException):
    """外部服务调用异常"""

    def __init__(self, message: str, service_name: str = None, url: str = None):
        details = {}
        if service_name:
            details["service"] = service_name
        if url:
            details["url"] = url[:100]
        super().__init__(message, code="EXTERNAL_SERVICE_ERROR", details=details)


class HttpRequestException(ExternalServiceException):
    """HTTP 请求异常"""

    def __init__(self, message: str, url: str = None, status_code: int = None):
        super().__init__(message, service_name="HTTP", url=url)
        self.code = "HTTP_REQUEST_ERROR"
        if status_code:
            self.details["status_code"] = status_code


class JsonParseException(AutoTestBaseException):
    """JSON 解析异常"""

    def __init__(self, message: str, raw_data: str = None):
        details = {}
        if raw_data:
            details["raw_data_preview"] = raw_data[:100] + "..." if len(raw_data) > 100 else raw_data
        super().__init__(message, code="JSON_PARSE_ERROR", details=details)
