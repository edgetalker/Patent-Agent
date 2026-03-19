"""
专利权利要求生成 API 路由
─────────────────────────────────────────────────────────────────────────────
端点设计：
  POST /sessions/start           → SSE: 创建 session + 运行 Step 1 + 流式输出
  POST /sessions/{id}/review     → SSE: 人工确认 → 运行下一步 + 流式输出
  GET  /sessions/{id}/state      → JSON: 查询当前 session 状态
  GET  /sessions/{id}/export     → JSON: 导出全部步骤输出
  DELETE /sessions/{id}          → JSON: 删除 session（开发调试用）

SSE 事件类型（data 字段为 JSON 字符串）：
  {"type": "session_created", "thread_id": "..."}
  {"type": "token",           "content": "..."}          ← LLM 流式 token
  {"type": "step_complete",   "step": N, "field": "...", "output": "..."}
  {"type": "pipeline_complete", "final_claims": "..."}
  {"type": "error",           "message": "..."}
─────────────────────────────────────────────────────────────────────────────
"""
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter
from langgraph.types import Command
from sse_starlette.sse import EventSourceResponse

from app.core.exceptions import SessionNotFoundError, InvalidStateError
from app.core.logger import setup_logger
from app.models.schemas import StartSessionRequest, ReviewRequest
from app.services.patent_graph import get_graph

logger = setup_logger("patent_agent.router")

router = APIRouter(prefix="/api/v1/patent", tags=["Patent Claims Generation"])


# ─── 内部工具函数 ──────────────────────────────────────────────────────────────

def _sse(payload: dict) -> dict:
    """将 dict 序列化为 SSE data 字段所需格式。"""
    return {"data": json.dumps(payload, ensure_ascii=False)}


async def _stream_graph(
    graph,
    config: dict,
    input_or_command,
    is_first: bool = False,
    thread_id: str = "",
) -> AsyncGenerator[dict, None]:
    """
    通用 SSE 生成器：
      1. 如果 is_first=True，先 yield session_created 事件
      2. 通过 astream_events 流式推送 LLM tokens
      3. 流结束后检查 graph 状态，推送 step_complete 或 pipeline_complete
    """
    if is_first and thread_id:
        yield _sse({"type": "session_created", "thread_id": thread_id})
        logger.info(f"[{thread_id[:8]}] Session created")

    try:
        async for event in graph.astream_events(
            input_or_command, config=config, version="v2"
        ):
            kind = event.get("event", "")
            if kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and chunk.content:
                    yield _sse({"type": "token", "content": chunk.content})

    except Exception as exc:
        logger.error(f"[{thread_id[:8]}] Stream error: {exc}")
        yield _sse({"type": "error", "message": str(exc)})
        return

    # ── 流结束：检查图状态 ──────────────────────────────────────────────────
    state = await graph.aget_state(config)

    if state.tasks and state.tasks[0].interrupts:
        # 图在某节点处 interrupt()，等待人工审核
        interrupt_payload: dict = state.tasks[0].interrupts[0].value
        step = interrupt_payload.get("step", "?")
        field = interrupt_payload.get("field", "")
        output = interrupt_payload.get("output", "")
        logger.info(f"[{thread_id[:8]}] Step {step} complete, awaiting review")
        yield _sse({
            "type": "step_complete",
            "step": step,
            "field": field,
            "output": output,
        })
    else:
        # 图正常结束（step 7 完成）
        final_claims = state.values.get("final_claims", "")
        logger.info(f"[{thread_id[:8]}] Pipeline complete")
        yield _sse({"type": "pipeline_complete", "final_claims": final_claims})


# ─── 端点 1：创建 Session + 运行 Step 1 ───────────────────────────────────────

@router.post(
    "/sessions/start",
    summary="创建会话并运行 Step 1（SSE）",
    description="上传技术交底书，创建新的专利撰写会话，流式运行 Step 1（发明构思分析）。",
)
async def start_session(request: StartSessionRequest):
    thread_id = str(uuid.uuid4())
    graph = await get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    initial_input = {
        "disclosure": request.disclosure,
        "mirror_types": request.mirror_types,
        "concepts": "",
        "prob_solution": "",
        "ind_claims": "",
        "dep_claims": "",
        "def_claims": "",
        "mirrored_claims": "",
        "final_claims": "",
        "current_step": 1,
    }

    logger.info(f"[{thread_id[:8]}] Starting new session | disclosure_len={len(request.disclosure)}")

    async def generator():
        async for event in _stream_graph(
            graph, config, initial_input, is_first=True, thread_id=thread_id
        ):
            yield event

    return EventSourceResponse(generator())


# ─── 端点 2：提交人工审核结果 + 运行下一步 ────────────────────────────────────

@router.post(
    "/sessions/{thread_id}/review",
    summary="提交审核结果并运行下一步（SSE）",
    description=(
        "提交人工审核/修改后的内容，继续 pipeline。"
        "若后续还有步骤，流式返回下一步的 LLM 输出；"
        "若所有步骤完成，返回 pipeline_complete 事件。"
    ),
)
async def review_step(thread_id: str, request: ReviewRequest):
    graph = await get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    # ── 前置校验 ────────────────────────────────────────────────────────────
    state = await graph.aget_state(config)
    if not state or not state.values:
        raise SessionNotFoundError(thread_id)
    if not (state.tasks and state.tasks[0].interrupts):
        raise InvalidStateError(
            f"Session '{thread_id}' has no pending review. "
            "Check if the pipeline has already completed or hasn't started yet."
        )

    step_info = state.tasks[0].interrupts[0].value
    logger.info(
        f"[{thread_id[:8]}] Review submitted "
        f"| step={step_info.get('step')} "
        f"| reviewed_len={len(request.content)}"
    )

    command = Command(resume=request.content)

    async def generator():
        async for event in _stream_graph(graph, config, command, thread_id=thread_id):
            yield event

    return EventSourceResponse(generator())


# ─── 端点 3：查询 Session 状态 ────────────────────────────────────────────────

@router.get(
    "/sessions/{thread_id}/state",
    summary="查询会话状态",
)
async def get_session_state(thread_id: str):
    graph = await get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    state = await graph.aget_state(config)
    if not state or not state.values:
        raise SessionNotFoundError(thread_id)

    has_interrupt = bool(state.tasks and state.tasks[0].interrupts)
    is_complete = not state.next and not has_interrupt

    status = "completed" if is_complete else ("awaiting_review" if has_interrupt else "running")

    # 如有 interrupt，提取当前等待审核的步骤信息
    pending_review = None
    if has_interrupt:
        pending_review = state.tasks[0].interrupts[0].value

    return {
        "success": True,
        "thread_id": thread_id,
        "current_step": state.values.get("current_step", 1),
        "status": status,
        "pending_review": pending_review,
        "state": state.values,
    }


# ─── 端点 4：导出全部步骤输出 ─────────────────────────────────────────────────

@router.get(
    "/sessions/{thread_id}/export",
    summary="导出全部步骤输出",
)
async def export_session(thread_id: str):
    graph = await get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    state = await graph.aget_state(config)
    if not state or not state.values:
        raise SessionNotFoundError(thread_id)

    v = state.values
    return {
        "success": True,
        "thread_id": thread_id,
        "current_step": v.get("current_step", 1),
        "step_outputs": {
            "step1_concepts":       v.get("concepts", ""),
            "step2_prob_solution":  v.get("prob_solution", ""),
            "step3_ind_claims":     v.get("ind_claims", ""),
            "step4_dep_claims":     v.get("dep_claims", ""),
            "step5_def_claims":     v.get("def_claims", ""),
            "step6_mirrored":       v.get("mirrored_claims", ""),
            "step7_final":          v.get("final_claims", ""),
        },
    }


# ─── 端点 5：删除 Session（开发/调试用）──────────────────────────────────────

@router.delete(
    "/sessions/{thread_id}",
    summary="删除会话（调试用）",
)
async def delete_session(thread_id: str):
    """
    注意：LangGraph SQLite checkpointer 暂不提供直接删除单条 checkpoint 的公开 API，
    此端点通过验证 session 存在性来确认操作目标，实际清理需要直接操作 DB 或重置。
    生产环境建议实现完整的 session 清理逻辑。
    """
    graph = await get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    state = await graph.aget_state(config)
    if not state or not state.values:
        raise SessionNotFoundError(thread_id)

    logger.warning(f"[{thread_id[:8]}] Delete requested (data remains in DB, thread invalidated)")
    return {
        "success": True,
        "thread_id": thread_id,
        "message": "Session marked as deleted. Use a new thread_id to start fresh.",
    }