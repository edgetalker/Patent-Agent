from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ─── 请求体 ───────────────────────────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    disclosure: str = Field(
        ...,
        min_length=50,
        description="技术交底书全文内容",
        examples=["本发明涉及一种..."],
    )
    mirror_types: str = Field(
        default="方法",
        description="步骤6 镜像权利要求类型，以英文分号分隔。如 '方法' 或 '装置;系统'",
    )


class ReviewRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        description="代理人审核/修改后的文本内容，将作为本步骤的最终输出传入下一步",
    )


# ─── 响应体 ───────────────────────────────────────────────────────────────────

class SessionStateResponse(BaseModel):
    success: bool = True
    thread_id: str
    current_step: int
    status: str  # "awaiting_review" | "completed" | "error"
    state: dict


class ExportResponse(BaseModel):
    success: bool = True
    thread_id: str
    step_outputs: dict


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
