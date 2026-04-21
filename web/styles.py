"""
界面样式 - 水墨丹青风格
"""

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Ma+Shan+Zheng&family=Noto+Serif+SC:wght@400;600;700&family=ZCOOL+XiaoWei&display=swap');

    /* ========== 根变量 ========== */
    :root {
        --paper-light: #faf8f5;
        --paper: #f5f0e6;
        --paper-dark: #e8e0d0;
        --ink-black: #1a1a1a;
        --ink-dark: #2d2d2d;
        --ink-medium: #4a4a4a;
        --gold: #b8860b;
        --gold-light: #daa520;
        --vermillion: #c73e3a;
        --jade: #5a8f7b;
        --mist: rgba(0, 0, 0, 0.03);
        --shadow-ink: rgba(0, 0, 0, 0.1);
    }

    /* ========== 全局样式 ========== */
    html, body, .main {
        background: var(--paper-light) !important;
        color: var(--ink-dark) !important;
        font-family: 'Noto Serif SC', serif !important;
    }

    .main > div {
        padding-top: 0 !important;
    }

    #MainMenu, footer, header {
        visibility: hidden;
    }
    .stDeployButton {
        display: none !important;
    }

    /* ========== 侧边栏样式 ========== */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--paper) 0%, var(--paper-dark) 100%) !important;
        border-right: 1px solid rgba(184, 134, 11, 0.2) !important;
    }

    section[data-testid="stSidebar"] .element-container {
        color: var(--ink-dark) !important;
    }

    .sidebar-title {
        text-align: center;
        padding: 1.5rem 0.5rem;
        border-bottom: 1px solid rgba(184, 134, 11, 0.3);
        margin-bottom: 1rem;
    }

    .sidebar-title h1 {
        font-family: 'Ma Shan Zheng', cursive !important;
        font-size: 2.2rem !important;
        color: var(--gold) !important;
        margin: 0 !important;
        text-shadow: 0 2px 10px rgba(184, 134, 11, 0.2);
        letter-spacing: 0.1em;
    }

    .sidebar-title p {
        color: rgba(45, 45, 45, 0.6) !important;
        font-size: 0.85rem !important;
        margin-top: 0.5rem !important;
        font-style: italic;
    }

    .stats-card {
        display: flex;
        justify-content: space-around;
        padding: 1rem;
        background: linear-gradient(135deg, rgba(184, 134, 11, 0.1) 0%, rgba(184, 134, 11, 0.05) 100%);
        border: 1px solid rgba(184, 134, 11, 0.2);
        border-radius: 12px;
        margin: 1rem 0;
    }

    .stat-item {
        text-align: center;
    }

    .stat-number {
        font-family: 'ZCOOL XiaoWei', serif;
        font-size: 2rem;
        color: var(--gold);
        text-shadow: 0 0 20px rgba(184, 134, 11, 0.3);
    }

    .stat-label {
        font-size: 0.7rem;
        color: rgba(45, 45, 45, 0.5);
        letter-spacing: 0.15em;
    }

    .stExpander {
        background: var(--paper-light) !important;
        border: 1px solid rgba(184, 134, 11, 0.15) !important;
        border-radius: 8px !important;
        margin-bottom: 0.5rem !important;
        overflow: hidden;
        transition: all 0.3s ease;
    }

    .stExpander:hover {
        border-color: rgba(184, 134, 11, 0.4) !important;
        box-shadow: 0 4px 20px rgba(184, 134, 11, 0.1);
    }

    .stExpander summary {
        font-family: 'ZCOOL XiaoWei', serif !important;
        font-size: 1rem !important;
        color: var(--gold) !important;
        padding: 0.75rem 1rem !important;
        background: rgba(184, 134, 11, 0.05) !important;
    }

    .stExpander summary:hover {
        background: rgba(184, 134, 11, 0.1) !important;
    }

    .stButton button {
        background: linear-gradient(135deg, rgba(184, 134, 11, 0.1) 0%, rgba(184, 134, 11, 0.05) 100%) !important;
        border: 1px solid rgba(184, 134, 11, 0.3) !important;
        color: var(--ink-dark) !important;
        font-family: 'Noto Serif SC', serif !important;
        font-size: 0.95rem !important;
        padding: 0.5rem 1rem !important;
        border-radius: 6px !important;
        transition: all 0.3s ease !important;
        width: 100% !important;
    }

    .stButton button:hover {
        background: linear-gradient(135deg, rgba(184, 134, 11, 0.25) 0%, rgba(184, 134, 11, 0.15) 100%) !important;
        border-color: var(--gold) !important;
        transform: translateX(5px);
        box-shadow: 0 4px 15px rgba(184, 134, 11, 0.15);
    }

    .char-avatar {
        font-size: 2rem;
        text-align: center;
        filter: drop-shadow(0 2px 8px rgba(0,0,0,0.15));
    }

    .char-title {
        font-size: 0.7rem;
        color: rgba(45, 45, 45, 0.5);
        margin-top: 0.2rem;
    }

    /* ========== 主内容区 ========== */
    .welcome-container {
        text-align: center;
        padding: 4rem 2rem;
        position: relative;
    }

    .welcome-container::before {
        content: '';
        position: absolute;
        top: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 80%;
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--gold), transparent);
    }

    .welcome-title {
        font-family: 'Ma Shan Zheng', cursive !important;
        font-size: 4rem !important;
        color: var(--gold) !important;
        text-shadow: 0 4px 30px rgba(184, 134, 11, 0.3);
        margin-bottom: 1rem !important;
        letter-spacing: 0.15em;
        animation: fadeInUp 1s ease;
    }

    .welcome-subtitle {
        font-size: 1.2rem;
        color: rgba(45, 45, 45, 0.6);
        font-style: italic;
        margin-bottom: 3rem;
        animation: fadeInUp 1s ease 0.2s both;
    }

    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .recommend-section {
        margin-top: 2rem;
    }

    .recommend-title {
        font-family: 'ZCOOL XiaoWei', serif;
        font-size: 1.5rem;
        color: var(--gold);
        text-align: center;
        margin-bottom: 1.5rem;
        position: relative;
    }

    .recommend-title::before,
    .recommend-title::after {
        content: '◆';
        margin: 0 1rem;
        color: rgba(184, 134, 11, 0.5);
    }

    .recommend-card {
        background: linear-gradient(145deg, var(--paper-light) 0%, var(--paper) 100%);
        border: 1px solid rgba(184, 134, 11, 0.2);
        border-radius: 12px;
        padding: 1.5rem 1rem;
        text-align: center;
        cursor: pointer;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }

    .recommend-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, transparent, var(--gold), transparent);
        opacity: 0;
        transition: opacity 0.3s;
    }

    .recommend-card:hover {
        transform: translateY(-8px);
        border-color: var(--gold);
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1), 0 0 30px rgba(184, 134, 11, 0.1);
    }

    .recommend-card:hover::before {
        opacity: 1;
    }

    .recommend-avatar {
        font-size: 3rem;
        margin-bottom: 0.5rem;
        filter: drop-shadow(0 4px 8px rgba(0,0,0,0.15));
    }

    .recommend-name {
        font-family: 'ZCOOL XiaoWei', serif;
        font-size: 1.2rem;
        color: var(--ink-dark);
        margin-bottom: 0.3rem;
    }

    .recommend-dynasty {
        font-size: 0.75rem;
        color: var(--gold);
        opacity: 0.8;
    }

    /* ========== 人物信息卡片 ========== */
    .character-profile {
        display: flex;
        gap: 2rem;
        padding: 2rem;
        background: linear-gradient(135deg, var(--paper-light) 0%, var(--paper) 100%);
        border: 1px solid rgba(184, 134, 11, 0.2);
        border-radius: 16px;
        margin-bottom: 2rem;
        position: relative;
        overflow: hidden;
        animation: slideIn 0.5s ease;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    }

    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(-20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .character-profile::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, var(--vermillion), var(--gold), var(--jade));
    }

    .profile-avatar-section {
        text-align: center;
        min-width: 180px;
    }

    .profile-avatar {
        font-size: 5rem;
        filter: drop-shadow(0 8px 16px rgba(0,0,0,0.15));
        animation: float 3s ease-in-out infinite;
    }

    @keyframes float {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-10px); }
    }

    .profile-name {
        font-family: 'Ma Shan Zheng', cursive;
        font-size: 2.5rem;
        color: var(--gold);
        margin-top: 0.5rem;
        text-shadow: 0 2px 10px rgba(184, 134, 11, 0.2);
    }

    .profile-title {
        font-size: 1rem;
        color: rgba(45, 45, 45, 0.6);
        margin-top: 0.3rem;
    }

    .profile-meta {
        display: flex;
        gap: 1.5rem;
        margin-top: 1rem;
        justify-content: center;
    }

    .meta-item {
        font-size: 0.85rem;
        color: rgba(45, 45, 45, 0.5);
    }

    .meta-item strong {
        color: var(--gold);
    }

    .profile-info-section {
        flex: 1;
    }

    .info-section-title {
        font-family: 'ZCOOL XiaoWei', serif;
        font-size: 1.2rem;
        color: var(--gold);
        margin-bottom: 0.75rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .info-section-title::before {
        content: '〢';
        color: var(--vermillion);
    }

    .profile-bio {
        color: rgba(45, 45, 45, 0.8);
        line-height: 1.8;
        font-size: 0.95rem;
    }

    .quote-container {
        margin-top: 1.5rem;
        padding: 1rem;
        background: rgba(184, 134, 11, 0.05);
        border-left: 3px solid var(--gold);
        border-radius: 0 8px 8px 0;
    }

    .quote-text {
        font-style: italic;
        color: rgba(45, 45, 45, 0.7);
        font-size: 0.9rem;
        line-height: 1.6;
    }

    .quote-text::before {
        content: '"';
        font-size: 1.5rem;
        color: var(--gold);
        margin-right: 0.3rem;
    }

    /* ========== 对话消息 ========== */
    .stChatMessage {
        background: transparent !important;
        padding: 1rem !important;
        border-radius: 12px !important;
        margin-bottom: 1rem !important;
    }

    .stChatMessage[data-testid="user-message"] {
        background: linear-gradient(135deg, rgba(90, 143, 123, 0.1) 0%, rgba(90, 143, 123, 0.05) 100%) !important;
        border: 1px solid rgba(90, 143, 123, 0.2) !important;
    }

    .stChatMessage[data-testid="assistant-message"] {
        background: linear-gradient(135deg, rgba(184, 134, 11, 0.08) 0%, rgba(184, 134, 11, 0.02) 100%) !important;
        border: 1px solid rgba(184, 134, 11, 0.15) !important;
    }

    .stChatMessage p {
        color: var(--ink-dark) !important;
        line-height: 1.8 !important;
    }

    /* 输入框 */
    .stChatInput {
        border: 1px solid rgba(184, 134, 11, 0.3) !important;
        border-radius: 12px !important;
        background: var(--paper) !important;
    }

    .stChatInput textarea {
        background: transparent !important;
        color: var(--ink-dark) !important;
        font-family: 'Noto Serif SC', serif !important;
    }

    .stChatInput textarea::placeholder {
        color: rgba(45, 45, 45, 0.4) !important;
    }

    /* 史料来源面板 */
    .source-panel {
        margin-top: 1rem;
        padding: 1rem;
        background: rgba(184, 134, 11, 0.05);
        border-radius: 8px;
        border-left: 3px solid var(--jade);
    }

    .source-title {
        font-family: 'ZCOOL XiaoWei', serif;
        color: var(--jade);
        margin-bottom: 0.5rem;
    }

    .source-item {
        padding: 0.3rem 0;
        font-size: 0.85rem;
    }

    .source-index {
        color: var(--gold);
        font-weight: bold;
    }

    .source-link {
        color: var(--ink-dark);
        text-decoration: none;
    }

    .source-link:hover {
        color: var(--gold);
        text-decoration: underline;
    }

    .source-from {
        color: rgba(45, 45, 45, 0.5);
        font-style: italic;
    }

    /* 分隔线 */
    .divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(184, 134, 11, 0.3), transparent);
        margin: 2rem 0;
    }

    /* 水墨背景装饰 */
    .ink-decoration {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        pointer-events: none;
        z-index: -1;
        opacity: 0.03;
        background-image:
            radial-gradient(ellipse at 20% 30%, rgba(184, 134, 11, 0.3) 0%, transparent 50%),
            radial-gradient(ellipse at 80% 70%, rgba(90, 143, 123, 0.2) 0%, transparent 50%),
            radial-gradient(ellipse at 50% 50%, rgba(199, 62, 58, 0.1) 0%, transparent 70%);
    }

    /* 滚动条 */
    ::-webkit-scrollbar {
        width: 8px;
    }

    ::-webkit-scrollbar-track {
        background: var(--paper-dark);
    }

    ::-webkit-scrollbar-thumb {
        background: rgba(184, 134, 11, 0.3);
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: rgba(184, 134, 11, 0.5);
    }
</style>
"""
