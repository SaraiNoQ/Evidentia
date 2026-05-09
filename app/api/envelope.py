from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


def request_id(request: Request) -> str:
    return request.headers.get("x-request-id", "req_local")


def success(data: Any, request: Request) -> dict[str, Any]:
    return {"data": data, "meta": {"request_id": request_id(request)}}


def error_response(
    *,
    code: str,
    message: str,
    request: Request,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
            "meta": {"request_id": request_id(request)},
        },
    )
