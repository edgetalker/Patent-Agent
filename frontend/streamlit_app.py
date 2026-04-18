"""
知识产权智能体平台 - Streamlit 前端
─────────────────────────────────────────────────────────────────────────────
运行方式：
  streamlit run frontend/streamlit_app.py

依赖：
  pip install -r requirements-frontend.txt

后端需在 http://localhost:8000 运行
─────────────────────────────────────────────────────────────────────────────
"""

import json
import time
import requests
import streamlit as st

# ─── 配置 ──────────────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8000/api/v1/patent"

STEPS = {
    1: {"title": "发明构思分析",    "field": "concepts",        "icon": "🧠"},
    2: {"title": "问题-解决方案",   "field": "prob_solution",   "icon": "🎯"},
    3: {"title": "独立权利要求",    "field": "ind_claims",      "icon": "📋"},
    4: {"title": "从属权利要求",    "field": "dep_claims",      "icon": "🔗"},
    5: {"title": "定义权利要求",    "field": "def_claims",      "icon": "📖"},
    6: {"title": "镜像权利要求",    "field": "mirrored_claims", "icon": "🪞"},
    7: {"title": "最终优化",        "field": "final_claims",    "icon": "✨"},
}

# ─── 页面配置 ──────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="知识产权智能体平台",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",  # 强制展开，用户可手动折叠
)

# ─── 全局样式 ──────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* 全局字体与背景 */
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Noto+Serif+SC:wght@400;600&display=swap');

html, body, [class*="css"] {
    background-color: #0d1117;
    color: #c9d1d9;
}

/* Header */
.ip-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 0 1.5rem 0;
    border-bottom: 1px solid #21262d;
    margin-bottom: 1.5rem;
}
.ip-header h1 {
    font-family: 'Noto Serif SC', serif;
    font-size: 1.4rem;
    font-weight: 600;
    color: #e6edf3;
    margin: 0;
    letter-spacing: 0.05em;
}
.ip-session-badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: #8b949e;
    background: #161b22;
    border: 1px solid #30363d;
    padding: 4px 10px;
    border-radius: 20px;
}

/* 步骤卡片 */
.step-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 8px;
    margin-bottom: 4px;
    font-size: 0.85rem;
    transition: background 0.2s;
}
.step-item.active {
    background: #1f2937;
    border-left: 3px solid #58a6ff;
    color: #58a6ff;
    font-weight: 500;
}
.step-item.done {
    background: #0d1f12;
    border-left: 3px solid #3fb950;
    color: #3fb950;
}
.step-item.pending {
    color: #484f58;
    border-left: 3px solid transparent;
}
.step-num {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    width: 20px;
    text-align: center;
}

/* 输出区域 */
.output-box {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    font-size: 0.88rem;
    line-height: 1.7;
    min-height: 200px;
    white-space: pre-wrap;
    font-family: 'JetBrains Mono', monospace;
    color: #c9d1d9;
}

/* 步骤标题 */
.step-title-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 1rem;
}
.step-title-bar .step-badge {
    background: #1f2937;
    border: 1px solid #30363d;
    color: #58a6ff;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    padding: 3px 10px;
    border-radius: 20px;
}
.step-title-bar h3 {
    font-family: 'Noto Serif SC', serif;
    font-size: 1.05rem;
    color: #e6edf3;
    margin: 0;
}

/* 状态标签 */
.status-tag {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-family: 'JetBrains Mono', monospace;
    margin-bottom: 1rem;
}
.status-generating { background: #1f2937; color: #58a6ff; border: 1px solid #1d4ed8; }
.status-review     { background: #1c1407; color: #d29922; border: 1px solid #9e6a03; }
.status-done       { background: #0d1f12; color: #3fb950; border: 1px solid #2ea043; }

/* 按钮覆写 */
div.stButton > button {
    background: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 0.4rem 1.2rem;
    font-size: 0.85rem;
    transition: all 0.2s;
}
div.stButton > button:hover {
    background: #30363d;
    border-color: #58a6ff;
    color: #58a6ff;
}
div.stButton > button[kind="primary"] {
    background: #1a4a8a;
    border-color: #58a6ff;
    color: #58a6ff;
}
div.stButton > button[kind="primary"]:hover {
    background: #1d58a8;
}

/* 侧边栏 */
[data-testid="stSidebar"] {
    background: #0d1117 !important;
    border-right: 1px solid #21262d;
}

/* textarea */
textarea {
    background: #161b22 !important;
    color: #c9d1d9 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem !important;
}

/* 分割线 */
hr { border-color: #21262d !important; }

/* Final output */
.final-card {
    background: #0d1f12;
    border: 1px solid #2ea043;
    border-radius: 10px;
    padding: 1.5rem;
    margin-top: 1rem;
}
.final-card h4 {
    color: #3fb950;
    font-family: 'Noto Serif SC', serif;
    margin-bottom: 1rem;
}

/* 隐藏 Streamlit 默认元素，保留侧边栏展开按钮 */
#MainMenu, footer { visibility: hidden; }

/* 侧边栏折叠/展开按钮始终可见（兼容多版本 Streamlit） */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
button[kind="header"],
.st-emotion-cache-eczf16,
section[data-testid="stSidebarCollapsedControl"] {
    visibility: visible !important;
    display: flex !important;
    opacity: 1 !important;
}

/* 保留 header 区域高度但隐藏内容（防止按钮被裁剪） */
header[data-testid="stHeader"] {
    background: transparent !important;
}
header[data-testid="stHeader"] > div:first-child {
    visibility: hidden;
}
header[data-testid="stHeader"] button {
    visibility: visible !important;
}
</style>
""", unsafe_allow_html=True)


# ─── Session State 初始化 ──────────────────────────────────────────────────────

def init_state():
    defaults = {
        "thread_id":       None,
        "current_step":    0,       # 0 = 未开始
        "status":          "idle",  # idle | generating | review | completed
        "step_outputs":    {},      # {step_num: content}
        "pending_output":  "",      # 当前步骤 LLM 原始输出（待审核）
        "pending_step":    None,    # 当前待审核步骤编号
        "stream_buffer":   "",      # 实时 token 缓冲
        "final_claims":    "",
        "error":           None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ─── SSE 工具函数 ──────────────────────────────────────────────────────────────

def parse_sse_stream(response):
    """解析 SSE 响应，逐行 yield dict。"""
    for raw_line in response.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        if line.startswith("data:"):
            data_str = line[5:].strip()
            if data_str:
                try:
                    yield json.loads(data_str)
                except json.JSONDecodeError:
                    pass


def stream_start_session(disclosure: str, mirror_types: str):
    """
    调用 /sessions/start，流式处理 SSE 事件。
    将 token 和控制事件写入 session_state。
    """
    url = f"{API_BASE}/sessions/start"
    payload = {"disclosure": disclosure, "mirror_types": mirror_types}

    st.session_state.status = "generating"
    st.session_state.stream_buffer = ""
    st.session_state.error = None

    try:
        with requests.post(url, json=payload, stream=True, timeout=180) as resp:
            resp.raise_for_status()
            for event in parse_sse_stream(resp):
                _handle_sse_event(event)
    except requests.RequestException as e:
        st.session_state.status = "idle"
        st.session_state.error = f"连接后端失败：{e}"


def stream_review(content: str):
    """
    调用 /sessions/{id}/review，提交审核内容并流式处理下一步。
    """
    thread_id = st.session_state.thread_id
    url = f"{API_BASE}/sessions/{thread_id}/review"
    payload = {"content": content}

    st.session_state.status = "generating"
    st.session_state.stream_buffer = ""
    st.session_state.error = None

    try:
        with requests.post(url, json=payload, stream=True, timeout=180) as resp:
            resp.raise_for_status()
            for event in parse_sse_stream(resp):
                _handle_sse_event(event)
    except requests.RequestException as e:
        st.session_state.status = "idle"
        st.session_state.error = f"提交审核失败：{e}"


def _handle_sse_event(event: dict):
    """根据 SSE 事件类型更新 session_state。"""
    etype = event.get("type")

    if etype == "session_created":
        st.session_state.thread_id = event.get("thread_id")
        st.session_state.current_step = 1

    elif etype == "token":
        st.session_state.stream_buffer += event.get("content", "")

    elif etype == "step_complete":
        step = event.get("step")
        output = event.get("output", "")
        st.session_state.step_outputs[step] = output
        st.session_state.pending_output = output
        st.session_state.pending_step = step
        st.session_state.current_step = step
        st.session_state.status = "review"
        st.session_state.stream_buffer = ""

    elif etype == "pipeline_complete":
        st.session_state.final_claims = event.get("final_claims", "")
        st.session_state.status = "completed"
        st.session_state.stream_buffer = ""

    elif etype == "error":
        st.session_state.error = event.get("message", "未知错误")
        st.session_state.status = "idle"


# ─── 侧边栏 ───────────────────────────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.markdown("### ⚖️ 知识产权智能体")
        st.markdown("---")

        # 步骤进度
        st.markdown("**撰写进度**")
        current = st.session_state.current_step
        status = st.session_state.status

        for num, info in STEPS.items():
            if num < current or (num == current and status == "review"):
                css = "done"
                indicator = "✓"
            elif num == current and status == "generating":
                css = "active"
                indicator = "⟳"
            elif num == current and status == "review":
                css = "active"
                indicator = "👁"
            else:
                css = "pending"
                indicator = str(num)

            st.markdown(
                f'<div class="step-item {css}">'
                f'<span class="step-num">{indicator}</span>'
                f'{info["icon"]} {info["title"]}'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # 操作区
        if st.button("🔄 新建会话", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        if st.session_state.status == "completed":
            export_data = json.dumps(
                {
                    "thread_id": st.session_state.thread_id,
                    "step_outputs": {
                        str(k): v
                        for k, v in st.session_state.step_outputs.items()
                    },
                    "final_claims": st.session_state.final_claims,
                },
                ensure_ascii=False,
                indent=2,
            )
            st.download_button(
                "📥 导出结果 (JSON)",
                data=export_data,
                file_name=f"patent_{st.session_state.thread_id[:8]}.json",
                mime="application/json",
                use_container_width=True,
            )

        # Session ID
        if st.session_state.thread_id:
            st.markdown("---")
            st.markdown(
                f'<div class="ip-session-badge">🔑 {st.session_state.thread_id[:16]}…</div>',
                unsafe_allow_html=True,
            )

        # 错误提示
        if st.session_state.error:
            st.error(st.session_state.error)


# ─── 主区域 ───────────────────────────────────────────────────────────────────

def render_main():
    # Header
    st.markdown(
        '<div class="ip-header">'
        '<h1>知识产权智能体平台</h1>'
        '<span style="color:#484f58;font-size:0.8rem;">Patent Claims Generation · HITL Pipeline</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    status = st.session_state.status

    # ── 初始输入界面 ──────────────────────────────────────────────────────────
    if status == "idle" and st.session_state.thread_id is None:
        render_input_panel()

    # ── 流式生成中 ────────────────────────────────────────────────────────────
    elif status == "generating":
        render_generating_panel()

    # ── 等待人工审核 ──────────────────────────────────────────────────────────
    elif status == "review":
        render_review_panel()

    # ── 流程完成 ──────────────────────────────────────────────────────────────
    elif status == "completed":
        render_completed_panel()


def render_input_panel():
    """初始输入面板"""
    st.markdown("#### 📄 技术交底书输入")
    st.markdown(
        '<p style="color:#8b949e;font-size:0.85rem;margin-bottom:1rem;">'
        "输入技术交底书，智能体将自动完成 7 步专利权利要求撰写流程，每步支持人工审核修改。"
        "</p>",
        unsafe_allow_html=True,
    )

    disclosure = st.text_area(
        "技术交底书",
        placeholder="请输入发明技术交底书全文内容（至少 50 字）……",
        height=280,
        label_visibility="collapsed",
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        mirror_types = st.text_input(
            "镜像权利要求类型",
            value="装置",
            help="Step 6 生成的镜像类型，如：装置 / 系统 / 装置;系统",
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        start_btn = st.button("🚀 开始撰写", type="primary", use_container_width=True)

    if start_btn:
        if len(disclosure.strip()) < 50:
            st.warning("⚠️ 技术交底书内容太短，请至少输入 50 字。")
        else:
            with st.spinner("正在启动智能体 Pipeline…"):
                stream_start_session(disclosure.strip(), mirror_types.strip())
            st.rerun()


def render_generating_panel():
    """流式生成面板"""
    step = st.session_state.current_step
    if step in STEPS:
        info = STEPS[step]
        st.markdown(
            f'<div class="step-title-bar">'
            f'<span class="step-badge">Step {step} / 7</span>'
            f'<h3>{info["icon"]} {info["title"]}</h3>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<span class="status-tag status-generating">⟳ AI 生成中…</span>',
        unsafe_allow_html=True,
    )

    # 实时 token 流显示
    output_placeholder = st.empty()

    # 轮询 stream_buffer 直到状态变化
    while st.session_state.status == "generating":
        current_buffer = st.session_state.stream_buffer
        output_placeholder.markdown(
            f'<div class="output-box">{current_buffer}▌</div>',
            unsafe_allow_html=True,
        )
        time.sleep(0.1)
        st.rerun()

    st.rerun()


def render_review_panel():
    """人工审核面板"""
    step = st.session_state.pending_step
    if step not in STEPS:
        return

    info = STEPS[step]

    st.markdown(
        f'<div class="step-title-bar">'
        f'<span class="step-badge">Step {step} / 7</span>'
        f'<h3>{info["icon"]} {info["title"]}</h3>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<span class="status-tag status-review">👁 待人工审核</span>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color:#8b949e;font-size:0.82rem;margin-bottom:0.8rem;">'
        "以下为 AI 生成内容，您可以直接编辑修改，确认后继续下一步。"
        "</p>",
        unsafe_allow_html=True,
    )

    edited = st.text_area(
        "审核内容",
        value=st.session_state.pending_output,
        height=400,
        label_visibility="collapsed",
        key=f"review_input_{step}",
    )

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        confirm_btn = st.button(
            f"✅ 确认并继续 Step {step + 1}" if step < 7 else "✅ 确认并完成",
            type="primary",
            use_container_width=True,
        )
    with col2:
        pass  # 预留重新生成按钮位置

    if confirm_btn:
        with st.spinner("提交审核，运行下一步…"):
            stream_review(edited)
        st.rerun()

    # 历史步骤折叠展示
    if st.session_state.step_outputs:
        with st.expander("📚 查看历史步骤输出", expanded=False):
            for s_num, s_content in sorted(st.session_state.step_outputs.items()):
                if s_num != step:
                    s_info = STEPS.get(s_num, {})
                    st.markdown(
                        f"**Step {s_num} — {s_info.get('title', '')}**"
                    )
                    st.text(s_content[:500] + ("…" if len(s_content) > 500 else ""))
                    st.markdown("---")


def render_completed_panel():
    """流程完成面板"""
    st.markdown(
        '<span class="status-tag status-done">✅ 权利要求撰写完成</span>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="final-card">'
        '<h4>📋 最终权利要求套件</h4>'
        f'<div style="white-space:pre-wrap;font-size:0.87rem;line-height:1.8;font-family:\'JetBrains Mono\',monospace;">'
        f'{st.session_state.final_claims}'
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 导出区 ────────────────────────────────────────────────────────────────
    st.markdown(
        '<p style="color:#8b949e;font-size:0.82rem;margin-bottom:0.6rem;">导出结果</p>',
        unsafe_allow_html=True,
    )

    tid = st.session_state.thread_id[:8]

    # TXT：仅最终权利要求
    txt_content = st.session_state.final_claims
    
    # TXT完整版：7步全部输出
    full_txt_parts = []
    for s_num, s_content in sorted(st.session_state.step_outputs.items()):
        s_info = STEPS.get(s_num, {})
        full_txt_parts.append(
            f"{'='*60}\n"
            f"Step {s_num} — {s_info.get('title', '')}\n"
            f"{'='*60}\n"
            f"{s_content}\n"
        )
    full_txt_parts.append(
        f"{'='*60}\n最终权利要求套件\n{'='*60}\n{st.session_state.final_claims}"
    )
    full_txt_content = "\n\n".join(full_txt_parts)

    # JSON：完整数据
    json_content = json.dumps(
        {
            "thread_id": st.session_state.thread_id,
            "step_outputs": {str(k): v for k, v in st.session_state.step_outputs.items()},
            "final_claims": st.session_state.final_claims,
        },
        ensure_ascii=False,
        indent=2,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "📄 导出权利要求 (.txt)",
            data=txt_content.encode("utf-8"),
            file_name=f"claims_{tid}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            "📑 导出完整报告 (.txt)",
            data=full_txt_content.encode("utf-8"),
            file_name=f"patent_report_{tid}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with col3:
        st.download_button(
            "🗂 导出数据 (.json)",
            data=json_content.encode("utf-8"),
            file_name=f"patent_{tid}.json",
            mime="application/json",
            use_container_width=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # 各步骤展开
    with st.expander("📚 查看完整撰写过程（7步详情）", expanded=False):
        for s_num, s_content in sorted(st.session_state.step_outputs.items()):
            s_info = STEPS.get(s_num, {})
            st.markdown(
                f'<span class="status-tag status-done">'
                f'Step {s_num} — {s_info.get("icon","")} {s_info.get("title","")}'
                f'</span>',
                unsafe_allow_html=True,
            )
            st.text_area(
                f"step_{s_num}",
                value=s_content,
                height=200,
                label_visibility="collapsed",
                key=f"final_view_{s_num}",
            )


# ─── 入口 ──────────────────────────────────────────────────────────────────────

render_sidebar()
render_main()