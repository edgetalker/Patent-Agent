"""
Patent Agent API - FastAPI 入口
─────────────────────────────────────────────────────────────────────────────
启动方式：
  uvicorn app.main:app --reload --port 8000

API 文档：
  http://localhost:8000/docs       (Swagger UI)
  http://localhost:8000/redoc      (ReDoc)
─────────────────────────────────────────────────────────────────────────────
"""
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logger import logger, setup_logger
from app.routers import patent
from app.services.patent_graph import init_graph, close_graph

settings = get_settings()

# 为三方库设置合适日志级别（避免过多噪音）
setup_logger("httpx",        level=30)   # WARNING
setup_logger("langchain",    level=30)
setup_logger("langgraph",    level=20 if settings.debug else 30)


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    logger.info(f"{'='*60}")
    logger.info(f"  {settings.app_name} v{settings.app_version}")
    logger.info(f"  debug={settings.debug} | db={settings.db_path}")
    logger.info(f"{'='*60}")

    await init_graph()
    logger.info("All services initialized. Ready to serve.")
    yield

    # ── Shutdown ──
    logger.info("Shutting down services...")
    await close_graph()
    logger.info("Shutdown complete.")


# ─── App 初始化 ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "基于 LangGraph HITL + DeepSeek API 的专利权利要求智能撰写系统。\n\n"
        "**工作流程：** 技术交底书 → 7步撰写（每步含人工审核节点）→ 最终权利要求套件"
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ─── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Exception Handlers ───────────────────────────────────────────────────────

register_exception_handlers(app)


# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(patent.router)


# ─── 基础端点 ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/health", tags=["System"], summary="健康检查")
async def health_check():
    return {
        "status": "ok",
        "version": settings.app_version,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": f"{settings.app_name} is running",
        "docs": "/docs",
    }