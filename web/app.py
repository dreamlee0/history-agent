"""
Streamlit Web应用 - 历史人物对话
水墨丹青风格界面 + RAG知识溯源 + SQLite持久化
"""
import os
import sys
import hashlib
import uuid
import html as html_mod

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

# set_page_config 必须是脚本的第一条 Streamlit 命令：放在最顶部。
# 原因：下方 st.secrets 桥接在本地无 secrets.toml 时会先 st.error 入队一个
# delta，若 set_page_config 在其之后调用会抛 "can only be called once"
# （Streamlit 1.32 的 _set_page_config_allowed 只在每次 run 的 reset 时重置）。
st.set_page_config(
    page_title="历史人物对话 · 水墨丹青",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 将 Streamlit Secrets 桥接到环境变量，供 pydantic-settings 读取
# (.env 不会部署到云端，密钥需配在 Streamlit Cloud 的 Secrets 中)
# 注意：Streamlit 1.32 在本地无 secrets.toml 时，访问 st.secrets 会先入队一个
# st.error 警报——即使外层 try/except 吞掉异常也拦不住渲染，导致欢迎页顶部
# 出现红条并泄漏本地绝对路径。故先探测 secrets.toml 是否存在，不存在则跳过。
_secrets_candidates = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".streamlit", "secrets.toml"),
    os.path.join(os.path.expanduser("~"), ".streamlit", "secrets.toml"),
]
if any(os.path.exists(p) for p in _secrets_candidates):
    try:
        for _k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "EMBEDDING_MODEL", "HF_ENDPOINT"):
            if _k in st.secrets:
                os.environ.setdefault(_k, str(st.secrets[_k]))
    except Exception:
        pass

from src.characters import character_manager
from src.agents import AgentManager
from src.retrievers.vector_store import VectorStoreManager
from src.database.db import DatabaseManager

# 导入CSS样式
from web.styles import CUSTOM_CSS


def get_session_id():
    """获取浏览器会话标识（稳定，不随 rerun 变化）。

    优先使用官方 st.context API（Streamlit >= 1.35）；旧版本（本项目钉的
    1.32.0）没有该 API，回退到 st.runtime.scriptrunner（Streamlit 内部接口，
    新版本已移除但旧版仍可用）。两者都拿不到会话标识时，生成随机 UUID：
    避免多个浏览器会话退回到同一个 "default_user" 导致用户之间数据串扰。
    """
    if "session_id" not in st.session_state:
        session_id = None
        try:
            # 特性探测：st.context 在 Streamlit 1.35+ 提供官方会话上下文
            ctx = getattr(st, "context", None)
            if ctx is not None:
                session_id = getattr(ctx, "session_id", None)
        except Exception:
            session_id = None

        if not session_id:
            try:
                ctx = st.runtime.scriptrunner.get_script_run_ctx()
                if ctx:
                    session_id = ctx.session_id
            except Exception:
                session_id = None

        if session_id:
            st.session_state.session_id = hashlib.md5(
                session_id.encode()
            ).hexdigest()[:16]
        else:
            # 拿不到会话标识（非 Streamlit 环境 / 脚本模式）：
            # 生成随机 UUID，宁可每次不同也不让所有用户共用同一 ID。
            st.session_state.session_id = uuid.uuid4().hex[:16]
    return st.session_state.session_id


def _format_time(ts: str) -> str:
    """把 SQLite 时间戳（YYYY-MM-DD HH:MM:SS）压缩为 MM-DD HH:MM 展示。"""
    if not ts:
        return ""
    return ts[:16][5:] if len(ts) >= 16 else ts[:10]


def _source_parts(src: dict) -> tuple:
    """把一条来源拆成 (标题文本, 元信息文本, url)。

    数据源双轨：真实史源 → 标题取 source，元信息为 朝代·《书·篇卷》；
    persona（内置摘要）→ 标题取 title，元信息为「内置摘要」。
    无书/篇时退回 source，与旧版一致。
    """
    url = src.get("url", "")
    if src.get("doc_type") == "historical":
        book = (src.get("book") or "").strip()
        chapter = (src.get("chapter") or "").strip()
        dynasty = (src.get("dynasty") or "").strip()
        source = (src.get("source") or "未知").strip()
        if book:
            loc = f"《{book}"
            if chapter:
                loc += f"·{chapter}"
            loc += "》"
            attr = f"{dynasty}·{loc}" if dynasty else loc
        else:
            attr = ""
        return source, attr, url
    return (src.get("title") or "未知").strip(), "内置摘要", url


def _render_sources_html(sources: list) -> str:
    """把来源列表渲染成结构化溯源条目（.src-item 行，配合「参考史料」折叠面板）。

    为什么需要：参考资料标题来自知识文件元数据，属外部输入；在
    unsafe_allow_html=True 下直出会构成存储型 XSS 面，故先 html.escape。
    URL 非空时渲染为带 rel=noopener 的新窗口链接，方便溯源跳转。
    """
    rows = []
    for i, src in enumerate(sources, 1):
        label, attr, url = _source_parts(src)
        label = html_mod.escape(label)
        if url:
            url = html_mod.escape(url, quote=True)
            link = (
                f'<a class="src-link" href="{url}" target="_blank" '
                f'rel="noopener noreferrer">{label}</a>'
            )
        else:
            link = label
        attr_html = (
            f'<span class="src-attr">{html_mod.escape(attr)}</span>' if attr else ""
        )
        rows.append(
            f'<div class="src-item">'
            f'<span class="src-idx">{i}</span>'
            f'<div class="src-body">{link}{attr_html}</div>'
            f"</div>"
        )
    return "\n".join(rows)


# 最多在 session_state 里缓存多少个角色的消息（防无限增长，见 _prune_stale_messages）
MAX_CACHED_CHARACTER_MESSAGES = 10


def _prune_stale_messages(keep_name: str):
    """清理不活跃角色的消息缓存，只保留当前角色。

    为什么需要：st.session_state.messages 按角色名累积，长期使用后每个角色
    的整段对话历史都常驻会话存储，session_state 会无限增长。
    仅在缓存角色数超过阈值时裁剪一次（保留当前角色、删除其余），
    避免频繁切换人物时过早丢弃尚未落库的草稿对话。
    """
    if len(st.session_state.messages) <= MAX_CACHED_CHARACTER_MESSAGES:
        return
    for name in list(st.session_state.messages.keys()):
        if name != keep_name:
            del st.session_state.messages[name]


def init_app():
    """初始化应用"""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown('<div class="ink-decoration"></div>', unsafe_allow_html=True)

    # 初始化数据库
    if "db_manager" not in st.session_state:
        st.session_state.db_manager = DatabaseManager()

    if "entered" not in st.session_state:
        # 开始界面门禁：未点击「开始对话」前只渲染落地页
        st.session_state.entered = False
    if "current_character" not in st.session_state:
        st.session_state.current_character = None
    if "messages" not in st.session_state:
        st.session_state.messages = {}
    if "current_conversation_id" not in st.session_state:
        st.session_state.current_conversation_id = None
    if "agent_manager" not in st.session_state:
        vector_store = None
        try:
            from pathlib import Path

            vector_store = VectorStoreManager()
            chunk_count = vector_store.get_document_count()

            # 真实史料文档数 = 知识库目录下的文件数（非 chunk 数），
            # 用于界面展示；chunk 数是切分后的片段数，两者含义不同。
            knowledge_dir = Path("./data/knowledge")
            file_count = (
                len(list(knowledge_dir.glob("*.txt")))
                if knowledge_dir.exists()
                else 0
            )

            if chunk_count == 0:
                if knowledge_dir.exists() and file_count:
                    with st.spinner("首次运行，正在构建知识库..."):
                        from src.retrievers.vector_store import load_knowledge_files

                        documents = load_knowledge_files(str(knowledge_dir))
                        if documents:
                            chunk_count = vector_store.add_documents(documents)
                            st.success(f"知识库构建完成，共 {file_count} 篇史料文档")
                else:
                    vector_store = None
                    file_count = 0

            st.session_state.knowledge_count = file_count

        except Exception as e:
            st.warning(f"知识库初始化失败: {e}")
            vector_store = None
            st.session_state.knowledge_count = 0

        st.session_state.agent_manager = AgentManager(
            vector_store, st.session_state.db_manager
        )


def render_sidebar(entered: bool = True):
    """渲染侧边栏。

    entered=False（开始界面阶段）时不渲染任何侧栏内容：开始界面是整屏沉浸式
    落地页，侧栏整体隐藏（隐藏样式由 render_start_screen 注入，见其文档注释），
    进入后才显示品牌/统计/历史对话/人物选择。
    """
    if not entered:
        return

    db = st.session_state.db_manager
    session_id = get_session_id()

    with st.sidebar:
        st.markdown("""
        <div class="sidebar-title">
            <h1>历史人物对话</h1>
            <p>穿越五千年，与先贤对话</p>
        </div>
        """, unsafe_allow_html=True)

        # 统计
        total = character_manager.get_count()
        dynasties = character_manager.get_characters_by_dynasty()
        stats = db.get_stats(session_id)

        st.markdown(f"""
        <div class="stats-card">
            <div class="stat-item">
                <div class="stat-number">{total}</div>
                <div class="stat-label">历史人物</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{len(dynasties)}</div>
                <div class="stat-label">朝代</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{stats['total_conversations']}</div>
                <div class="stat-label">对话次数</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ─── 正在对话的角色（当前选中提示） ───
        cur_char = st.session_state.current_character
        if cur_char:
            char = character_manager.get_character(cur_char)
            if char:
                st.markdown(f"""
                <div class="now-chat">
                    <span class="now-chat-avatar">{char.avatar}</span>
                    <span>
                        <span class="now-chat-name">{html_mod.escape(char.name)}</span>
                        <span class="now-chat-meta">{html_mod.escape(char.dynasty)} · {html_mod.escape(char.title)}</span>
                    </span>
                </div>
                """, unsafe_allow_html=True)

        # ─── 历史对话（放在人物选择前面，方便查看） ───
        st.markdown("---")
        st.markdown('<div class="sidebar-section-title">历史对话</div>', unsafe_allow_html=True)
        conversations = db.get_conversations(session_id, limit=10)
        if conversations:
            for conv in conversations:
                char_name = conv["character_name"]
                char = character_manager.get_character(char_name)
                avatar = char.avatar if char else "💬"
                col1, col2 = st.columns([5, 1])
                with col1:
                    label = f"{avatar} {conv['title'][:18]}"
                    if st.button(label, key=f"conv_{conv['id']}", use_container_width=True):
                        st.session_state.current_character = char_name
                        st.session_state.current_conversation_id = conv["id"]
                        messages = db.get_messages(conv["id"])
                        st.session_state.messages[char_name] = [
                            {"role": m["role"], "content": m["content"], "sources": m.get("sources", [])}
                            for m in messages
                        ]
                        agent = st.session_state.agent_manager.get_agent(char_name)
                        if agent:
                            agent.load_history(conv["id"], get_session_id())
                        st.rerun()
                with col2:
                    if st.button("X", key=f"del_{conv['id']}", help="删除"):
                        db.delete_conversation(conv["id"])
                        # 同步清理该角色的内存记忆，与「删除对话」按钮语义一致：
                        # 避免删除后残留上下文在下次聊天/恢复时被复用（内存键=会话:人物，
                        # 只记录该人物最近活跃的对话）。
                        agent = st.session_state.agent_manager.get_agent(char_name)
                        if agent:
                            agent.clear_memory(session_id=get_session_id())
                        if st.session_state.current_conversation_id == conv["id"]:
                            st.session_state.current_conversation_id = None
                            st.session_state.messages.get(char_name, []).clear()
                        st.rerun()
                st.markdown(
                    f'<div class="conv-time">{_format_time(conv.get("updated_at") or "")}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<div style="color: #999; font-size: 0.85rem; padding: 0.5rem 0;">暂无历史对话</div>', unsafe_allow_html=True)

        # ─── 人物选择 ───
        st.markdown("---")
        st.markdown('<div class="sidebar-section-title">选择人物</div>', unsafe_allow_html=True)
        for dynasty, characters in dynasties.items():
            with st.expander(f"⏳ {dynasty} · {len(characters)}人"):
                for char in characters:
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        st.markdown(f'<div class="char-avatar">{char.avatar}</div>', unsafe_allow_html=True)
                    with col2:
                        if st.button(char.name, key=f"select_{char.name}", use_container_width=True):
                            st.session_state.current_character = char.name
                            st.session_state.current_conversation_id = None
                            if char.name not in st.session_state.messages:
                                st.session_state.messages[char.name] = []
                            _prune_stale_messages(char.name)
                            st.rerun()
                        st.markdown(f'<div class="char-title">{char.title}</div>', unsafe_allow_html=True)


def render_start_screen():
    """渲染开始界面（落地页）：整屏水墨山水沉浸式，点击「开始对话」后进入主界面。

    打开应用的第一屏。本函数同时注入隐藏侧栏的 CSS——Streamlit 侧栏是全局布局
    元素，无法按页面状态折叠，只能在开始界面阶段 display:none 藏掉；进入后
    （entered=True）不再注入，侧栏自然恢复。隐藏期间主区域由 flex 自动占满全宽，
    开始画面用 .start-screen 的 100vw 全出血铺开水墨背景（详见 styles.py）。
    点击按钮置 entered=True 后 rerun 进入选人/对话流程。
    """
    st.markdown(
        '<style>'
        'section[data-testid="stSidebar"],'
        'button[data-testid="stSidebarCollapsedControl"]'
        '{display:none!important;}'
        # 「开始对话」按钮上提到山峦下缘（开始页专属：负 margin 只在开始界面
        # 阶段注入，进入后不注入，不影响后续页面的 .stButton 布局）。
        '.stButton{margin-top:-3.5rem!important;}'
        '</style>',
        unsafe_allow_html=True,
    )

    total = character_manager.get_count()
    dynasty_count = len(character_manager.get_characters_by_dynasty())
    knowledge_count = st.session_state.get("knowledge_count", 0)
    kb_chip = (
        f'<span class="kb-chip ok">知识库已加载 {knowledge_count} 篇史料文档</span>'
        if knowledge_count > 0
        else '<span class="kb-chip err">知识库未加载，请运行 scripts/build_vector_db.py</span>'
    )

    st.markdown(f"""
    <div class="start-screen">
        <div class="paper-grain"></div>
        <div class="ink-sun"></div>
        <div class="mist mist-a"></div>
        <div class="mist mist-b"></div>
        <div class="mountain-far"></div>
        <div class="mountain-mid"></div>
        <div class="mountain-near"></div>
        <div class="water-band"></div>
        <div class="side-inscription">烟波浩渺<br/>与古为徒</div>
        <div class="colophon">大江东去浪淘尽<br/>千古风流人物</div>
        <div class="start-content">
            <div class="hero-seal"><span>对</span><span>话</span><span>千</span><span>年</span></div>
            <div class="hero-badge">千年对话 · 智能问答</div>
            <h1 class="welcome-title">历史人物对话</h1>
            <p class="welcome-subtitle">穿越五千年时光，与历史先贤促膝长谈</p>
            {kb_chip}
            <div class="hero-stats">
                <div class="hero-stat"><b>{total}</b><span>历史人物</span></div>
                <div class="hero-stat"><b>{dynasty_count}</b><span>朝代</span></div>
                <div class="hero-stat"><b>{knowledge_count}</b><span>史料文档</span></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 开始按钮单独居中一行（type="primary" → kind="primary"，样式见 styles.py）。
    # 不用 use_container_width：胶囊按钮按内容收缩、靠 CSS margin:auto 自身居中，
    # 否则会和样式里的 width:auto 打架，导致按钮贴在列内一侧。
    col_l, col_m, col_r = st.columns([1, 3, 1])
    with col_m:
        if st.button("🖌 开始对话", type="primary", key="start_enter"):
            st.session_state.entered = True
            st.rerun()


def render_welcome():
    """渲染欢迎页面"""
    # 顶部数字与知识库状态统一走新设计系统的组件类
    # （.hero-badge / .hero-stats / .kb-chip），替换旧的内联样式提示条。
    total = character_manager.get_count()
    dynasty_count = len(character_manager.get_characters_by_dynasty())
    knowledge_count = st.session_state.get("knowledge_count", 0)
    kb_chip = (
        f'<span class="kb-chip ok">知识库已加载 {knowledge_count} 篇史料文档</span>'
        if knowledge_count > 0
        else '<span class="kb-chip err">知识库未加载，请运行 scripts/build_vector_db.py</span>'
    )

    st.markdown(f"""
    <div class="welcome-container">
        <div class="hero-badge">千年对话 · 智能问答</div>
        <h1 class="welcome-title">历史人物对话</h1>
        <p class="welcome-subtitle">穿越五千年时光，与历史先贤促膝长谈</p>
        <div class="hero-stats">
            <div class="hero-stat"><b>{total}</b><span>历史人物</span></div>
            <div class="hero-stat"><b>{dynasty_count}</b><span>朝代</span></div>
            <div class="hero-stat"><b>{knowledge_count}</b><span>史料文档</span></div>
        </div>
        {kb_chip}
    </div>
    """, unsafe_allow_html=True)

    # 最近对话
    db = st.session_state.db_manager
    session_id = get_session_id()
    recent_convs = db.get_conversations(session_id, limit=3)
    if recent_convs:
        st.markdown("""
        <div class="recommend-section">
            <div class="recommend-title">最近对话</div>
        </div>
        """, unsafe_allow_html=True)
        cols = st.columns(min(len(recent_convs), 3))
        for i, conv in enumerate(recent_convs):
            char = character_manager.get_character(conv["character_name"])
            if char:
                with cols[i]:
                    st.markdown(f"""
                    <div class="recent-card">
                        <div class="recent-card-top">
                            <span class="recent-avatar">{char.avatar}</span>
                            <span class="recent-name">{html_mod.escape(char.name)}</span>
                            <span class="recent-char">{html_mod.escape(char.dynasty)}</span>
                            <span class="recent-time">{_format_time(conv.get("updated_at") or "")}</span>
                        </div>
                        <div class="recent-title">{html_mod.escape(conv["title"])}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("继续对话", key=f"resume_{conv['id']}", use_container_width=True):
                        st.session_state.current_character = char.name
                        st.session_state.current_conversation_id = conv["id"]
                        messages = db.get_messages(conv["id"])
                        st.session_state.messages[char.name] = [
                            {"role": m["role"], "content": m["content"], "sources": m.get("sources", [])}
                            for m in messages
                        ]
                        agent = st.session_state.agent_manager.get_agent(char.name)
                        if agent:
                            agent.load_history(conv["id"], get_session_id())
                        st.rerun()

    st.markdown("""
    <div class="recommend-section">
        <div class="recommend-title">推荐人物</div>
    </div>
    """, unsafe_allow_html=True)

    recommended = [
        ("孔子", "春秋", "🎓"),
        ("秦始皇", "秦朝", "👑"),
        ("李白", "唐朝", "🌙"),
        ("诸葛亮", "三国", "🪭"),
        ("苏轼", "北宋", "🎋"),
        ("孙中山", "民国", "🌅"),
    ]

    cols = st.columns(len(recommended))
    for i, (name, dynasty, avatar) in enumerate(recommended):
        char = character_manager.get_character(name)
        if char:
            # 推荐卡加一句人物名言（.rec-quote），来自本地 YAML（受信任），
            # 仍按纵深防御策略转义（与人物简介一致）。
            quote = char.famous_quotes[0] if char.famous_quotes else ""
            quote_html = (
                f'<div class="rec-quote">{html_mod.escape(quote)}</div>' if quote else ""
            )
            with cols[i]:
                st.markdown(f"""
                <div class="recommend-card">
                    <div class="recommend-avatar">{avatar}</div>
                    <div class="recommend-name">{html_mod.escape(name)}</div>
                    <div class="recommend-dynasty">{html_mod.escape(dynasty)}</div>
                    {quote_html}
                </div>
                """, unsafe_allow_html=True)
                if st.button("对话", key=f"rec_{name}", use_container_width=True):
                    st.session_state.current_character = name
                    st.session_state.current_conversation_id = None
                    if name not in st.session_state.messages:
                        st.session_state.messages[name] = []
                    _prune_stale_messages(name)
                    st.rerun()

    st.markdown(
        '<div class="welcome-hint">✦ 从侧栏或下方人物卡片中选择一位，开始对话 ✦</div>',
        unsafe_allow_html=True,
    )


def render_character_profile():
    """渲染人物档案"""
    char_name = st.session_state.current_character
    if not char_name:
        return

    char = character_manager.get_character(char_name)
    if not char:
        return

    # 人物档案内容来自本地 YAML 配置（受信任），但仍在 unsafe_allow_html 下
    # 做 HTML 转义（纵深防御），与参考资料标题的转义策略一致（L10）。
    bio = html_mod.escape(char.personality).replace(chr(10), '<br>')
    quotes = "".join(
        f'<p class="quote-text">{html_mod.escape(q)}</p>' for q in char.famous_quotes
    )

    st.markdown(f"""
    <div class="character-profile">
        <div class="profile-avatar-section">
            <div class="profile-avatar">{char.avatar}</div>
            <div class="profile-name">{char.name}</div>
            <div class="profile-title">{char.title}</div>
            <div class="profile-meta">
                <span class="meta-item"><strong>{char.dynasty}</strong></span>
                <span class="meta-item">{char.years}</span>
            </div>
        </div>
        <div class="profile-info-section">
            <div class="info-section-title">人物简介</div>
            <div class="profile-bio">{bio}</div>
            <div class="quote-container">
                <div class="info-section-title" style="margin-bottom: 0.5rem;">名言</div>
                {quotes}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_chat():
    """渲染对话区域"""
    char_name = st.session_state.current_character

    if not char_name:
        render_welcome()
        return

    char = character_manager.get_character(char_name)
    messages = st.session_state.messages.get(char_name, [])

    # 显示历史消息
    for msg in messages:
        with st.chat_message(msg["role"]):
            # assistant 消息带角色名头部（.chat-author），与实时回复保持一致
            if msg["role"] == "assistant" and char:
                st.markdown(f"""
                <div class="chat-author">
                    <span class="chat-author-name">{char.avatar} {html_mod.escape(char.name)}</span>
                    <span class="chat-author-meta">{html_mod.escape(char.dynasty)} · {html_mod.escape(char.title)}</span>
                </div>
                """, unsafe_allow_html=True)
            st.write(msg["content"])
            if "sources" in msg and msg["sources"]:
                with st.expander("参考史料"):
                    st.markdown(
                        _render_sources_html(msg["sources"]),
                        unsafe_allow_html=True
                    )

    # 输入框
    if prompt := st.chat_input(f"向{char_name}提问..."):
        with st.chat_message("user"):
            st.write(prompt)

        messages.append({"role": "user", "content": prompt, "sources": []})
        st.session_state.messages[char_name] = messages

        with st.chat_message("assistant"):
            st.markdown(f"""
            <div class="chat-author">
                <span class="chat-author-name">{char.avatar} {html_mod.escape(char.name)}</span>
                <span class="chat-author-meta">{html_mod.escape(char.dynasty)} · {html_mod.escape(char.title)}</span>
            </div>
            """, unsafe_allow_html=True)
            with st.spinner(f"{char.avatar} {char_name}正在思考..."):
                agent = st.session_state.agent_manager.get_agent(char_name)
                if agent:
                    try:
                        response, sources, conv_id = agent.chat(
                            prompt,
                            session_id=get_session_id(),
                            conversation_id=st.session_state.current_conversation_id,
                        )
                        st.session_state.current_conversation_id = conv_id
                        st.write(response)

                        if sources:
                            with st.expander("参考史料"):
                                st.markdown(
                                    _render_sources_html(sources),
                                    unsafe_allow_html=True
                                )

                        messages.append({
                            "role": "assistant",
                            "content": response,
                            "sources": sources
                        })
                        st.session_state.messages[char_name] = messages

                    except Exception as e:
                        st.error(f"对话出错: {e}")

    # 操作按钮
    if messages:
        # 分隔线自带操作条间距（.divider 墨线 + .chat-actions 顶部留白），
        # 用自闭合 div 而非跨 widget 开合 div，避免破坏 Streamlit 布局。
        st.markdown('<div class="divider chat-actions"></div>', unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
        with col1:
            if st.button("删除对话", use_container_width=True):
                # 语义修正：删除当前对话时连同 SQLite 记录一起删，保持与
                # 侧边栏历史列表联动，避免"只清 UI/内存、DB 残留"导致
                # 历史列表里还能点开已"清空"的旧消息。
                db = st.session_state.db_manager
                if st.session_state.current_conversation_id:
                    db.delete_conversation(st.session_state.current_conversation_id)
                st.session_state.messages[char_name] = []
                st.session_state.current_conversation_id = None
                agent = st.session_state.agent_manager.get_agent(char_name)
                if agent:
                    agent.clear_memory(session_id=get_session_id())
                st.rerun()
        with col2:
            if st.button("更换人物", use_container_width=True):
                st.session_state.current_character = None
                st.session_state.current_conversation_id = None
                st.rerun()
        with col3:
            from web.export_utils import export_to_markdown, export_to_pdf, get_download_filename

            export_option = st.selectbox(
                "导出格式",
                options=["不导出", "Markdown", "PDF"],
                key=f"export_{char_name}",
                label_visibility="collapsed"
            )

            if export_option == "Markdown":
                character_info = {
                    "dynasty": char.dynasty,
                    "title": char.title,
                    "years": char.years
                }
                md_content = export_to_markdown(char_name, messages, character_info)
                st.download_button(
                    label="下载MD",
                    data=md_content,
                    file_name=get_download_filename(char_name, "md"),
                    mime="text/markdown",
                    use_container_width=True
                )
            elif export_option == "PDF":
                try:
                    character_info = {
                        "dynasty": char.dynasty,
                        "title": char.title,
                        "years": char.years
                    }
                    pdf_bytes = export_to_pdf(char_name, messages, character_info)
                    st.download_button(
                        label="下载PDF",
                        data=pdf_bytes,
                        file_name=get_download_filename(char_name, "pdf"),
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as e:
                    st.warning(f"PDF导出失败: {e}")


def main():
    init_app()

    if not st.session_state.entered:
        # 开始界面阶段：侧栏只留品牌 + 主区域落地页
        render_sidebar(entered=False)
        render_start_screen()
        return

    render_sidebar(entered=True)

    if st.session_state.current_character:
        render_character_profile()
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    render_chat()


if __name__ == "__main__":
    main()
