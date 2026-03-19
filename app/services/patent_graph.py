"""
专利权利要求生成 LangGraph Pipeline
─────────────────────────────────────────────────────────────────────────────
设计原则：
  - 7个线性节点，对应撰写7步骤
  - 每个节点：LLM生成 → interrupt() 暂停等待人工审核 → 接收审核后内容 → 写入state
  - SQLite checkpointer 实现跨会话持久化
  - 使用工厂函数 _make_step_node() 消除重复代码（高内聚低耦合）

SSE Streaming 原理：
  astream_events() 会捕获节点内 LLM 调用产生的 on_chat_model_stream 事件，
  router 层将这些事件实时推送给前端。
─────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import aiosqlite
from typing import TypedDict, Optional, Callable, Awaitable

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt

from app.core.exceptions import LLMCallError
from app.core.logger import setup_logger
from app.prompts.patent_prompts import (
    build_step1_prompt,
    build_step2_prompt,
    build_step3_prompt,
    build_step4_prompt,
    build_step5_prompt,
    build_step6_prompt,
    build_step7_prompt,
)
from app.services.llm_client import get_llm

logger = setup_logger("patent_agent.graph")


# ─── State 定义 ───────────────────────────────────────────────────────────────

class PatentState(TypedDict):
    """整条 pipeline 的共享状态，由 SQLite checkpointer 持久化。"""
    disclosure: str          # 技术交底书（初始输入，全程不变）
    mirror_types: str        # 步骤6 镜像类型（初始输入，全程不变）

    concepts: str            # Step 1 输出：发明构思分析
    prob_solution: str       # Step 2 输出：问题-解决方案陈述
    ind_claims: str          # Step 3 输出：独立权利要求
    dep_claims: str          # Step 4 输出：从属权利要求
    def_claims: str          # Step 5 输出：定义权利要求
    mirrored_claims: str     # Step 6 输出：镜像权利要求（整合后的完整套件）
    final_claims: str        # Step 7 输出：最终优化权利要求

    current_step: int        # 当前执行步骤编号（1-7）


# ─── 辅助函数：拼接步骤3/4/5/7所需的"所有权利要求"文本 ────────────────────────

def _merge_claims(state: PatentState) -> str:
    """将 ind_claims + dep_claims + def_claims 合并为完整权利要求文本。"""
    parts = []
    if state.get("ind_claims"):
        parts.append(state["ind_claims"])
    if state.get("dep_claims"):
        parts.append(state["dep_claims"])
    if state.get("def_claims") and state["def_claims"] != "无需定义权利要求":
        parts.append(state["def_claims"])
    return "\n\n".join(parts)


# ─── 节点工厂（消除7个节点的重复代码）────────────────────────────────────────

def _make_step_node(
    step_num: int,
    output_field: str,
    prompt_builder: Callable[[PatentState], str],
    next_step: int,
):
    """
    工厂函数，生成标准步骤节点。

    参数:
        step_num     : 步骤编号（1-7），用于 interrupt payload 和日志
        output_field : 写入 state 的字段名（如 "concepts"）
        prompt_builder: 接收 state，返回 prompt 字符串
        next_step    : 本步骤完成后 current_step 应更新为的值
    """
    async def node(state: PatentState) -> dict:
        logger.info(f"[Step {step_num}] Starting | field={output_field}")

        try:
            llm = get_llm()
            prompt = prompt_builder(state)
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            raw_output: str = response.content
        except Exception as exc:
            logger.error(f"[Step {step_num}] LLM call failed: {exc}")
            raise LLMCallError(str(exc)) from exc

        logger.info(f"[Step {step_num}] LLM done | output_len={len(raw_output)}")

        # ── 在此暂停，等待人工审核 ──────────────────────────────────────────
        # interrupt() 会把 payload 存入 checkpoint，并挂起整个 graph。
        # Router 读取此 payload 后通过 SSE 发给前端。
        # 前端调用 /review 时，Command(resume=edited_content) 会让这里返回。
        reviewed: str = interrupt(
            {
                "step": step_num,
                "field": output_field,
                "output": raw_output,
            }
        )
        # ────────────────────────────────────────────────────────────────────

        logger.info(
            f"[Step {step_num}] Resumed with reviewed content "
            f"| reviewed_len={len(reviewed)}"
        )
        return {output_field: reviewed, "current_step": next_step}

    # 给节点函数命名，方便调试和日志
    node.__name__ = f"step{step_num}_node"
    return node


# ─── 各节点的 prompt_builder（适配不同入参）─────────────────────────────────

def _step1_builder(s: PatentState) -> str:
    return build_step1_prompt(s["disclosure"])

def _step2_builder(s: PatentState) -> str:
    return build_step2_prompt(s["concepts"], s["disclosure"])

def _step3_builder(s: PatentState) -> str:
    return build_step3_prompt(s["prob_solution"], s["disclosure"])

def _step4_builder(s: PatentState) -> str:
    return build_step4_prompt(s["ind_claims"], s["prob_solution"], s["disclosure"])

def _step5_builder(s: PatentState) -> str:
    all_claims = f"{s['ind_claims']}\n\n{s['dep_claims']}"
    return build_step5_prompt(all_claims, s["disclosure"])

def _step6_builder(s: PatentState) -> str:
    all_claims = _merge_claims(s)
    return build_step6_prompt(all_claims, s["mirror_types"])

def _step7_builder(s: PatentState) -> str:
    all_claims = s["mirrored_claims"]
    return build_step7_prompt(all_claims, s["prob_solution"], s["disclosure"])


# ─── 构建 Graph ───────────────────────────────────────────────────────────────

# (step_num, output_field, prompt_builder, next_step)
_STEP_CONFIGS = [
    (1, "concepts",         _step1_builder, 2),
    (2, "prob_solution",    _step2_builder, 3),
    (3, "ind_claims",       _step3_builder, 4),
    (4, "dep_claims",       _step4_builder, 5),
    (5, "def_claims",       _step5_builder, 6),
    (6, "mirrored_claims",  _step6_builder, 7),
    (7, "final_claims",     _step7_builder, 8),  # next_step=8 表示结束
]


def _build_patent_graph() -> StateGraph:
    builder = StateGraph(PatentState)

    node_names = []
    for step_num, field, prompt_fn, next_step in _STEP_CONFIGS:
        name = f"step{step_num}"
        node_fn = _make_step_node(step_num, field, prompt_fn, next_step)
        builder.add_node(name, node_fn)
        node_names.append(name)

    # Entry point
    builder.set_entry_point(node_names[0])

    # Linear edges: step1 → step2 → ... → step7 → END
    for i in range(len(node_names) - 1):
        builder.add_edge(node_names[i], node_names[i + 1])
    builder.add_edge(node_names[-1], END)

    return builder


# ─── 单例管理（全局 graph 实例 + checkpointer）─────────────────────────────

_graph = None
_checkpointer: Optional[AsyncSqliteSaver] = None


async def init_graph() -> None:
    """在 FastAPI lifespan 中调用，初始化 graph 和 SQLite checkpointer。"""
    global _graph, _checkpointer

    from app.config import get_settings
    settings = get_settings()

    logger.info(f"Initializing patent graph | db={settings.db_path}")
    conn = await aiosqlite.connect(settings.db_path)
    _checkpointer = AsyncSqliteSaver(conn)

    builder = _build_patent_graph()
    _graph = builder.compile(checkpointer=_checkpointer)
    logger.info("Patent graph initialized successfully")


async def get_graph():
    """获取已初始化的 graph 实例（懒加载兜底）。"""
    if _graph is None:
        await init_graph()
    return _graph


async def close_graph() -> None:
    """在 FastAPI shutdown 中调用，关闭 DB 连接。"""
    if _checkpointer and hasattr(_checkpointer, "conn"):
        await _checkpointer.conn.close()
        logger.info("SQLite checkpointer connection closed")