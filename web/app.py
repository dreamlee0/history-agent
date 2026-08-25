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

# 将 Streamlit Secrets 桥接到环境变量，供 pydantic-settings 读取
# (.env 不会部署到云端，密钥需配在 Streamlit Cloud 的 Secrets 中)
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


def _render_sources_html(sources: list) -> str:
    """把来源列表渲染成一行 HTML（标题已转义防 XSS，URL 生成可点击链接）。

    为什么需要：参考资料标题来自知识文件元数据，属外部输入；在
    unsafe_allow_html=True 下直出会构成存储型 XSS 面，故先 html.escape。
    URL 非空时渲染为带 rel=noopener 的新窗口链接，方便溯源跳转。
    """
    parts = []
    for src in sources:
        title = html_mod.escape(src.get("title", "未知"))
        url = src.get("url", "")
        if url:
            url = html_mod.escape(url, quote=True)
            parts.append(
                f'<a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>'
            )
        else:
            parts.append(title)
    return "参考资料: " + " | ".join(parts)


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
    st.set_page_config(
        page_title="历史人物对话 · 水墨丹青",
        page_icon="📜",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown('<div class="ink-decoration"></div>', unsafe_allow_html=True)

    # 初始化数据库
    if "db_manager" not in st.session_state:
        st.session_state.db_manager = DatabaseManager()

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


def render_sidebar():
    """渲染侧边栏"""
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

        # ─── 历史对话（放在人物选择前面，方便查看） ───
        st.markdown("---")
        st.markdown("### 历史对话")
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
        else:
            st.markdown('<div style="color: #999; font-size: 0.85rem; padding: 0.5rem 0;">暂无历史对话</div>', unsafe_allow_html=True)

        # ─── 人物选择 ───
        st.markdown("---")
        st.markdown("### 选择人物")
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


def render_welcome():
    """渲染欢迎页面"""
    st.markdown("""
    <div class="welcome-container">
        <h1 class="welcome-title">历史人物对话</h1>
        <p class="welcome-subtitle">穿越五千年时光，与历史先贤促膝长谈</p>
    </div>
    """, unsafe_allow_html=True)

    knowledge_count = st.session_state.get("knowledge_count", 0)
    if knowledge_count > 0:
        st.markdown(f"""
        <div style="text-align: center; margin: 1rem 0; padding: 0.5rem;
                    background: rgba(184, 134, 11, 0.1); border-radius: 8px;">
            <span style="color: var(--gold);">知识库已加载 {knowledge_count} 篇史料文档</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align: center; margin: 1rem 0; padding: 0.5rem;
                    background: rgba(199, 62, 58, 0.1); border-radius: 8px;">
            <span style="color: var(--vermillion);">知识库未加载，请运行 scripts/build_vector_db.py</span>
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
                    <div class="recommend-card">
                        <div class="recommend-avatar">{char.avatar}</div>
                        <div class="recommend-name">{char.name}</div>
                        <div class="recommend-dynasty">{conv['title'][:20]}</div>
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
            with cols[i]:
                st.markdown(f"""
                <div class="recommend-card">
                    <div class="recommend-avatar">{avatar}</div>
                    <div class="recommend-name">{name}</div>
                    <div class="recommend-dynasty">{dynasty}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("对话", key=f"rec_{name}", use_container_width=True):
                    st.session_state.current_character = name
                    st.session_state.current_conversation_id = None
                    if name not in st.session_state.messages:
                        st.session_state.messages[name] = []
                    _prune_stale_messages(name)
                    st.rerun()


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
            st.write(msg["content"])
            if "sources" in msg and msg["sources"]:
                st.markdown(
                    f'<div style="font-size: 0.75rem; color: #888; margin-top: 0.5rem;">'
                    f'{_render_sources_html(msg["sources"])}</div>',
                    unsafe_allow_html=True
                )

    # 输入框
    if prompt := st.chat_input(f"向{char_name}提问..."):
        with st.chat_message("user"):
            st.write(prompt)

        messages.append({"role": "user", "content": prompt, "sources": []})
        st.session_state.messages[char_name] = messages

        with st.chat_message("assistant"):
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
                            st.markdown(
                                f'<div style="font-size: 0.75rem; color: #888; margin-top: 0.5rem;">'
                                f'{_render_sources_html(sources)}</div>',
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
        st.markdown("---")
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
    render_sidebar()

    if st.session_state.current_character:
        render_character_profile()
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    render_chat()


if __name__ == "__main__":
    main()
