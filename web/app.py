"""
Streamlit Web应用 - 历史人物对话
水墨丹青风格界面 + RAG知识溯源
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from src.characters import character_manager
from src.agents import AgentManager
from src.retrievers.vector_store import VectorStoreManager

# 导入CSS样式
from web.styles import CUSTOM_CSS


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

    if "current_character" not in st.session_state:
        st.session_state.current_character = None
    if "messages" not in st.session_state:
        st.session_state.messages = {}
    if "agent_manager" not in st.session_state:
        # 初始化向量库
        vector_store = None
        try:
            vector_store = VectorStoreManager()
            doc_count = vector_store.get_document_count()

            # 如果向量库为空，尝试构建
            if doc_count == 0:
                from src.retrievers.vector_store import load_knowledge_files, build_vector_store
                import os
                from pathlib import Path

                # 检查知识文件是否存在
                knowledge_dir = Path("./data/knowledge")
                if knowledge_dir.exists() and list(knowledge_dir.glob("*.txt")):
                    with st.spinner("首次运行，正在构建知识库..."):
                        documents = load_knowledge_files(str(knowledge_dir))
                        if documents:
                            count = vector_store.add_documents(documents)
                            doc_count = count
                            st.success(f"知识库构建完成，共 {count} 个文档")
                else:
                    vector_store = None
                    doc_count = 0

            st.session_state.knowledge_count = doc_count

        except Exception as e:
            st.warning(f"知识库初始化失败: {e}")
            vector_store = None
            st.session_state.knowledge_count = 0

        st.session_state.agent_manager = AgentManager(vector_store)


def render_sidebar():
    """渲染侧边栏"""
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
        knowledge_count = st.session_state.get("knowledge_count", 0)

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
                <div class="stat-number">{knowledge_count}</div>
                <div class="stat-label">史料文档</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='margin: 1rem 0;'></div>", unsafe_allow_html=True)

        # 朝代列表
        for dynasty, characters in dynasties.items():
            with st.expander(f"⏳ {dynasty} · {len(characters)}人", expanded=False):
                for char in characters:
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        st.markdown(f'<div class="char-avatar">{char.avatar}</div>', unsafe_allow_html=True)
                    with col2:
                        if st.button(char.name, key=f"select_{char.name}", use_container_width=True):
                            st.session_state.current_character = char.name
                            if char.name not in st.session_state.messages:
                                st.session_state.messages[char.name] = []
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

    # 知识库状态
    knowledge_count = st.session_state.get("knowledge_count", 0)
    if knowledge_count > 0:
        st.markdown(f"""
        <div style="text-align: center; margin: 1rem 0; padding: 0.5rem;
                    background: rgba(184, 134, 11, 0.1); border-radius: 8px;">
            <span style="color: var(--gold);">📚 知识库已加载 {knowledge_count} 篇史料文档</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align: center; margin: 1rem 0; padding: 0.5rem;
                    background: rgba(199, 62, 58, 0.1); border-radius: 8px;">
            <span style="color: var(--vermillion);">⚠️ 知识库未加载，请运行 scripts/crawl_knowledge.py 和 scripts/build_vector_db.py</span>
        </div>
        """, unsafe_allow_html=True)

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
        ("康熙", "清朝", "🏯"),
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
                    if name not in st.session_state.messages:
                        st.session_state.messages[name] = []
                    st.rerun()


def render_character_profile():
    """渲染人物档案"""
    char_name = st.session_state.current_character
    if not char_name:
        return

    char = character_manager.get_character(char_name)
    if not char:
        return

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
            <div class="profile-bio">{char.personality.replace(chr(10), '<br>')}</div>
            <div class="quote-container">
                <div class="info-section-title" style="margin-bottom: 0.5rem;">名言</div>
                {''.join(f'<p class="quote-text">{q}</p>' for q in char.famous_quotes)}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_source_panel(sources: list):
    """渲染史料来源面板"""
    if not sources:
        return

    st.markdown("""
    <div class="source-panel">
        <div class="source-title">📚 参考史料</div>
    """, unsafe_allow_html=True)

    for src in sources:
        url = src.get("url", "")
        title = src.get("title", "未知")
        source = src.get("source", "未知")

        if url:
            st.markdown(f"""
            <div class="source-item">
                <span class="source-index">[{src.get('index', '')}]</span>
                <a href="{url}" target="_blank" class="source-link">{title}</a>
                <span class="source-from">- {source}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="source-item">
                <span class="source-index">[{src.get('index', '')}]</span>
                <span class="source-title-text">{title}</span>
                <span class="source-from">- {source}</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


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
            # 显示史料来源（小字显示）
            if "sources" in msg and msg["sources"]:
                sources_text = " | ".join([
                    f"{src.get('title', '未知')}" for src in msg["sources"]
                ])
                st.markdown(
                    f'<div style="font-size: 0.75rem; color: #888; margin-top: 0.5rem;">'
                    f'📖 参考资料: {sources_text}</div>',
                    unsafe_allow_html=True
                )

    # 输入框
    if prompt := st.chat_input(f"向{char_name}提问..."):
        # 用户消息
        with st.chat_message("user"):
            st.write(prompt)

        messages.append({"role": "user", "content": prompt, "sources": []})
        st.session_state.messages[char_name] = messages

        # AI回复
        with st.chat_message("assistant"):
            with st.spinner(f"{char.avatar} {char_name}正在思考..."):
                agent = st.session_state.agent_manager.get_agent(char_name)
                if agent:
                    try:
                        response, sources = agent.chat(prompt, session_id=char_name)
                        st.write(response)

                        # 显示史料来源（小字显示）
                        if sources:
                            sources_text = " | ".join([
                                f"{src.get('title', '未知')}" for src in sources
                            ])
                            st.markdown(
                                f'<div style="font-size: 0.75rem; color: #888; margin-top: 0.5rem;">'
                                f'📖 参考资料: {sources_text}</div>',
                                unsafe_allow_html=True
                            )

                        # 保存消息
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
            if st.button("🗑️ 清空对话", use_container_width=True):
                st.session_state.messages[char_name] = []
                agent = st.session_state.agent_manager.get_agent(char_name)
                if agent:
                    agent.clear_memory(session_id=char_name)
                st.rerun()
        with col2:
            if st.button("🔄 更换人物", use_container_width=True):
                st.session_state.current_character = None
                st.rerun()
        with col3:
            # 导出按钮
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
                    label="📄 下载MD",
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
                        label="📕 下载PDF",
                        data=pdf_bytes,
                        file_name=get_download_filename(char_name, "pdf"),
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as e:
                    st.warning(f"PDF导出需要安装reportlab: pip install reportlab")


def main():
    init_app()
    render_sidebar()

    if st.session_state.current_character:
        render_character_profile()
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    render_chat()


if __name__ == "__main__":
    main()
