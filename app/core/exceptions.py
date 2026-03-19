from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logger import logger


# ─── 自定义异常体系 ───────────────────────────────────────────────────────────

class PatentAgentError(Exception):
    """所有业务异常的基类"""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class SessionNotFoundError(PatentAgentError):
    def __init__(self, thread_id: str):
        super().__init__(
            message=f"Session '{thread_id}' not found",
            code="SESSION_NOT_FOUND",
            status_code=404,
        )


class LLMCallError(PatentAgentError):
    def __init__(self, detail: str):
        super().__init__(
            message=f"LLM call failed: {detail}",
            code="LLM_ERROR",
            status_code=502,
        )


class InvalidStateError(PatentAgentError):
    def __init__(self, detail: str):
        super().__init__(
            message=detail,
            code="INVALID_STATE",
            status_code=400,
        )


# ─── 注册到 FastAPI ───────────────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(PatentAgentError)
    async def patent_agent_error_handler(request: Request, exc: PatentAgentError):
        logger.warning(f"[{exc.code}] {exc.message} | path={request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {"code": exc.code, "message": exc.message},
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception on {request.url.path}: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"},
            },
        )