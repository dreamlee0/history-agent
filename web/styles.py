"""
界面样式 - 水墨丹青风格

设计约定：
- 颜色全部走 :root 变量（宣纸/墨色/金/黛绿/朱砂）
- 中文字体族通过 var(--font-*) 统一定义，Google Fonts 加载失败（离线演示）
  时自动回退到本地楷体/宋体栈，避免界面观感崩塌。
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
        --ink-soft: rgba(45, 45, 45, 0.55);
        --ink-faint: rgba(45, 45, 45, 0.38);
        --gold: #b8860b;
        --gold-light: #daa520;
        --vermillion: #c73e3a;
        --jade: #5a8f7b;
        --jade-soft: rgba(90, 143, 123, 0.35);
        --mist: rgba(0, 0, 0, 0.03);
        --shadow-ink: rgba(0, 0, 0, 0.1);

        /* 字体族（Google Fonts 缺失时回退本地 CJK 字体） */
        --font-call: 'Ma Shan Zheng', 'Kaiti SC', 'STKaiti', 'KaiTi',
                      'Noto Serif SC', 'Source Han Serif SC', serif;
        --font-label: 'ZCOOL XiaoWei', 'Kaiti SC', 'STKaiti', 'KaiTi',
                      'Noto Serif SC', 'Source Han Serif SC', serif;
        --font-body: 'Noto Serif SC', 'Source Han Serif SC',
                     'Noto Serif CJK SC', 'Songti SC', 'SimSun', serif;
    }

    /* ========== 全局样式 ========== */
    html, body, .main {
        background: var(--paper-light) !important;
        color: var(--ink-dark) !important;
        font-family: var(--font-body) !important;
    }

    /* 开始界面 100vw 全出血需要禁止横向滚动（进入后无副作用） */
    section[data-testid="stAppViewContainer"] {
        overflow-x: hidden;
    }

    .main > div {
        padding-top: 0 !important;
    }

    .main .block-container {
        max-width: 1180px;
        padding-top: 1rem;
        padding-bottom: 6rem;
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

    section[data-testid="stSidebar"] .block-container {
        max-width: none;
    }

    .sidebar-title {
        text-align: center;
        padding: 1.2rem 0.5rem 1rem;
        border-bottom: 1px solid rgba(184, 134, 11, 0.3);
        margin-bottom: 0.5rem;
    }

    .sidebar-title h1 {
        font-family: var(--font-call) !important;
        font-size: 2rem !important;
        color: var(--gold) !important;
        margin: 0 !important;
        text-shadow: 0 2px 10px rgba(184, 134, 11, 0.2);
        letter-spacing: 0.1em;
    }

    .sidebar-title p {
        color: var(--ink-soft) !important;
        font-size: 0.8rem !important;
        margin-top: 0.4rem !important;
        font-style: italic;
    }

    /* 侧栏次级标题 */
    .sidebar-section-title {
        font-family: var(--font-label);
        color: var(--ink-medium);
        font-size: 0.95rem;
        letter-spacing: 0.2em;
        padding-left: 0.25rem;
        margin: 0.5rem 0 0.25rem;
    }

    .sidebar-section-title::before {
        content: '✦ ';
        color: var(--gold);
        opacity: 0.7;
    }

    .stats-card {
        display: flex;
        justify-content: space-around;
        padding: 0.9rem 0.4rem;
        background: linear-gradient(135deg, rgba(184, 134, 11, 0.1) 0%, rgba(184, 134, 11, 0.05) 100%);
        border: 1px solid rgba(184, 134, 11, 0.2);
        border-radius: 12px;
        margin: 0.9rem 0;
    }

    .stat-item {
        text-align: center;
    }

    .stat-number {
        font-family: var(--font-label);
        font-size: 1.8rem;
        color: var(--gold);
        text-shadow: 0 0 20px rgba(184, 134, 11, 0.3);
        line-height: 1.2;
    }

    .stat-label {
        font-size: 0.68rem;
        color: var(--ink-soft);
        letter-spacing: 0.15em;
    }

    /* 正在对话的角色（当前选中提示） */
    .now-chat {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.55rem 0.75rem;
        margin: 0.4rem 0 0.6rem;
        background: linear-gradient(135deg, rgba(184, 134, 11, 0.14), rgba(184, 134, 11, 0.05));
        border: 1px solid rgba(184, 134, 11, 0.35);
        border-radius: 10px;
    }

    .now-chat-avatar {
        font-size: 1.6rem;
        line-height: 1;
    }

    .now-chat-name {
        font-family: var(--font-label);
        font-size: 1rem;
        color: var(--gold);
    }

    .now-chat-meta {
        font-size: 0.68rem;
        color: var(--ink-soft);
    }

    .stExpander {
        background: var(--paper-light) !important;
        border: 1px solid rgba(184, 134, 11, 0.15) !important;
        border-radius: 8px !important;
        margin-bottom: 0.5rem !important;
        transition: border-color 0.3s ease, box-shadow 0.3s ease;
        overflow: hidden;
    }

    .stExpander:hover {
        border-color: rgba(184, 134, 11, 0.4) !important;
        box-shadow: 0 4px 20px rgba(184, 134, 11, 0.1);
    }

    .stExpander summary {
        font-family: var(--font-label) !important;
        font-size: 1rem !important;
        color: var(--gold) !important;
        padding: 0.7rem 1rem !important;
        background: rgba(184, 134, 11, 0.05) !important;
        border-radius: 8px !important;
    }

    .stExpander summary:hover {
        background: rgba(184, 134, 11, 0.1) !important;
    }

    .stButton button {
        background: linear-gradient(135deg, rgba(184, 134, 11, 0.1) 0%, rgba(184, 134, 11, 0.05) 100%) !important;
        border: 1px solid rgba(184, 134, 11, 0.3) !important;
        color: var(--ink-dark) !important;
        font-family: var(--font-body) !important;
        font-size: 0.95rem !important;
        padding: 0.5rem 1rem !important;
        border-radius: 6px !important;
        transition: all 0.25s ease !important;
        width: 100% !important;
    }

    .stButton button:hover {
        background: linear-gradient(135deg, rgba(184, 134, 11, 0.25) 0%, rgba(184, 134, 11, 0.15) 100%) !important;
        border-color: var(--gold) !important;
        box-shadow: 0 4px 15px rgba(184, 134, 11, 0.15);
    }

    .char-avatar {
        font-size: 1.9rem;
        text-align: center;
        filter: drop-shadow(0 2px 8px rgba(0, 0, 0, 0.15));
    }

    .char-title {
        font-size: 0.7rem;
        color: var(--ink-faint);
        margin-top: 0.2rem;
    }

    /* 侧栏历史对话条目 */
    .conv-time {
        font-size: 0.7rem;
        color: var(--ink-faint);
        padding-top: 0.6rem;
        white-space: nowrap;
    }

    /* ========== 主内容区 / 开始界面 ========== */
    .welcome-container {
        text-align: center;
        padding: 2.2rem 1.5rem 1.2rem;
        position: relative;
    }

    .welcome-title {
        font-family: var(--font-call) !important;
        font-size: 3.6rem !important;
        color: var(--gold) !important;
        text-shadow: 0 4px 30px rgba(184, 134, 11, 0.3);
        margin: 0.4rem 0 1.6rem !important;
        letter-spacing: 0.18em;
        animation: fadeInUp 0.85s ease 0.7s both;
        position: relative;
    }

    /* 标题下方一笔淡金刷痕 */
    .welcome-title::after {
        content: '';
        position: absolute;
        left: 50%;
        bottom: -1.1rem;
        transform: translateX(-50%);
        width: 55%;
        height: 5px;
        border-radius: 999px;
        background: linear-gradient(90deg, transparent, rgba(184, 134, 11, 0.45) 18%, rgba(184, 134, 11, 0.55) 82%, transparent);
    }

    .welcome-subtitle {
        font-size: 1.05rem;
        color: var(--ink-soft);
        font-style: italic;
        margin: 0 auto 1.2rem !important;
        max-width: 46ch;
        letter-spacing: 0.08em;
        animation: fadeInUp 0.85s ease 0.85s both;
    }

    .hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.32rem 1.1rem;
        border: 1px solid rgba(184, 134, 11, 0.4);
        border-radius: 999px;
        color: var(--gold);
        font-size: 0.78rem;
        letter-spacing: 0.28em;
        background: rgba(184, 134, 11, 0.07);
        animation: fadeInUp 0.8s ease 0.55s both;
    }

    /* 朱砂印章「对话千年」（2×2 篆刻风，略旋转，做开始页顶部落款） */
    .hero-seal {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 3px;
        width: 72px;
        height: 72px;
        padding: 8px;
        margin: 0 auto 1.1rem;
        background: var(--vermillion);
        color: var(--paper-light);
        border-radius: 8px;
        box-shadow: 0 4px 16px rgba(199, 62, 58, 0.35), inset 0 0 0 1px rgba(250, 248, 245, 0.5);
        transform: rotate(-4deg);
        font-family: var(--font-call) !important;
        animation: sealStamp 0.55s cubic-bezier(0.22, 1, 0.36, 1) 0.4s both;
    }

    .hero-seal span {
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.3rem;
        line-height: 1;
        letter-spacing: 0.05em;
    }

    /* 知识库状态 chip */
    .kb-chip {
        display: inline-block;
        padding: 0.3rem 1rem;
        border-radius: 999px;
        font-size: 0.78rem;
        margin-top: 0.4rem;
        letter-spacing: 0.06em;
        animation: fadeInUp 0.8s ease 1s both;
    }

    .kb-chip.ok {
        color: var(--jade);
        background: rgba(90, 143, 123, 0.1);
        border: 1px solid rgba(90, 143, 123, 0.35);
    }

    .kb-chip.err {
        color: var(--vermillion);
        background: rgba(199, 62, 58, 0.08);
        border: 1px solid rgba(199, 62, 58, 0.35);
    }

    .hero-stats {
        display: flex;
        justify-content: center;
        gap: 3rem;
        margin: 1.8rem auto 0.4rem;
        flex-wrap: wrap;
        animation: fadeInUp 0.85s ease 1.15s both;
    }

    .hero-stat {
        position: relative;
        padding: 0 0.25rem;
    }

    /* 相邻数字之间竖线分隔 */
    .hero-stat + .hero-stat::before {
        content: '';
        position: absolute;
        left: -1.5rem;
        top: 50%;
        transform: translateY(-50%);
        width: 1px;
        height: 2.3rem;
        background: rgba(184, 134, 11, 0.3);
    }

    .hero-stat b {
        display: block;
        font-family: var(--font-label);
        font-size: 2.1rem;
        font-weight: 400;
        color: var(--gold);
        line-height: 1.25;
    }

    .hero-stat span {
        font-size: 0.72rem;
        color: var(--ink-soft);
        letter-spacing: 0.28em;
    }

    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    .recommend-section {
        margin-top: 2.4rem;
    }

    .recommend-title {
        font-family: var(--font-label);
        font-size: 1.4rem;
        font-weight: 400;
        color: var(--gold);
        text-align: center;
        margin-bottom: 1.4rem;
        position: relative;
        letter-spacing: 0.2em;
    }

    .recommend-title::before,
    .recommend-title::after {
        content: '◆';
        margin: 0 0.9rem;
        font-size: 0.7rem;
        color: rgba(184, 134, 11, 0.5);
        vertical-align: middle;
    }

    .recommend-card {
        background: linear-gradient(145deg, var(--paper-light) 0%, var(--paper) 100%);
        border: 1px solid rgba(184, 134, 11, 0.2);
        border-radius: 12px;
        padding: 1.2rem 1rem 1rem;
        text-align: center;
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
        height: 100%;
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
        transform: translateY(-6px);
        border-color: var(--gold);
        box-shadow: 0 18px 36px rgba(0, 0, 0, 0.09), 0 0 30px rgba(184, 134, 11, 0.1);
    }

    .recommend-card:hover::before {
        opacity: 1;
    }

    .recommend-avatar {
        font-size: 2.7rem;
        margin-bottom: 0.4rem;
        filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.15));
    }

    .recommend-name {
        font-family: var(--font-label);
        font-size: 1.15rem;
        color: var(--ink-dark);
        margin-bottom: 0.15rem;
        letter-spacing: 0.08em;
    }

    .recommend-dynasty {
        font-size: 0.72rem;
        color: var(--gold);
        opacity: 0.9;
        margin-bottom: 0.5rem;
    }

    /* 推荐卡内的一句话名言 */
    .rec-quote {
        font-size: 0.78rem;
        color: var(--ink-medium);
        line-height: 1.65;
        font-style: italic;
        padding: 0.4rem 0.5rem 0;
        border-top: 1px dashed rgba(184, 134, 11, 0.25);
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        min-height: 2.6em;
    }

    /* 最近对话卡片 */
    .recent-card {
        text-align: left;
        padding: 0.9rem 1rem;
        background: linear-gradient(145deg, var(--paper-light), var(--paper));
        border: 1px solid rgba(184, 134, 11, 0.18);
        border-radius: 12px;
        height: 100%;
        transition: all 0.3s ease;
    }

    .recent-card:hover {
        border-color: rgba(90, 143, 123, 0.5);
        box-shadow: 0 12px 24px rgba(0, 0, 0, 0.07);
    }

    .recent-card-top {
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }

    .recent-avatar {
        font-size: 1.8rem;
    }

    .recent-name {
        font-family: var(--font-label);
        font-size: 1.02rem;
        color: var(--ink-dark);
    }

    .recent-char {
        font-size: 0.72rem;
        color: var(--gold);
    }

    .recent-time {
        margin-left: auto;
        font-size: 0.68rem;
        color: var(--ink-faint);
        white-space: nowrap;
    }

    .recent-title {
        margin-top: 0.4rem;
        font-size: 0.82rem;
        color: var(--ink-medium);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .welcome-hint {
        text-align: center;
        color: var(--ink-faint);
        font-size: 0.78rem;
        margin-top: 2rem;
        letter-spacing: 0.1em;
    }

    /* ========== 开始界面（落地页）：水墨长卷 ========== */
    /* 整屏水墨长卷：left:50% + translateX(-50%) + width:100vw 全出血铺开，抵消
       .block-container 1180px 居中的两侧留白。层次自下而上：宣纸底色 → 三层墨色
       山峦（远/中/近，载入时从雾中升起）→ 山脚水雾 → 右上朱砂落日（呼吸）→
       飘动云雾 → 左右两侧竖排题跋 → 居中主内容（唯一正常流子元素，被 flex 垂直
       居中）→ 最上层 4% 宣纸颗粒噪声。除 .start-content 外全部绝对定位不占位。 */
    .start-screen {
        position: relative;
        left: 50%;
        transform: translateX(-50%);
        width: 100vw;
        min-height: calc(100vh - 8rem);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 3.5rem 1rem 2.5rem;
        overflow: hidden;
        background:
            radial-gradient(ellipse 62% 46% at 50% 40%, rgba(184, 134, 11, 0.07), transparent 72%),
            radial-gradient(ellipse 130% 55% at 50% 0%, rgba(0, 0, 0, 0.08), transparent 60%),
            linear-gradient(180deg, #efe9dc 0%, var(--paper-light) 52%, var(--paper) 100%);
    }

    /* 右上朱砂落日（淡金高光 + 晕环，缓慢呼吸） */
    .ink-sun {
        position: absolute;
        top: 8%;
        right: 13%;
        width: 118px;
        height: 118px;
        border-radius: 50%;
        z-index: 5;
        background:
            radial-gradient(circle at 42% 38%, rgba(255, 214, 150, 0.4) 0%, transparent 46%),
            radial-gradient(circle, rgba(199, 62, 58, 0.82) 0%, rgba(199, 62, 58, 0.3) 58%, rgba(199, 62, 58, 0.05) 78%, transparent 86%);
        box-shadow: 0 0 42px rgba(199, 62, 58, 0.22);
        filter: blur(1px);
        pointer-events: none;
        animation: sunBreathe 7s ease-in-out infinite;
    }

    @keyframes sunBreathe {
        0%, 100% { transform: scale(1);    opacity: 0.9; }
        50%      { transform: scale(1.07); opacity: 1; }
    }

    /* 远山（最淡最虚，像雾里的远影） */
    .mountain-far {
        position: absolute;
        left: 0;
        right: 0;
        bottom: 0;
        height: 52%;
        z-index: 1;
        background: linear-gradient(180deg, rgba(60, 60, 60, 0.05), rgba(60, 60, 60, 0.13));
        clip-path: polygon(0 74%, 5% 48%, 12% 66%, 20% 32%, 29% 60%, 38% 24%, 48% 54%, 57% 34%, 67% 62%, 76% 40%, 86% 64%, 94% 46%, 100% 58%, 100% 100%, 0 100%);
        pointer-events: none;
        animation: riseUp 1.1s ease 0.1s both;
    }

    /* 中山（中墨，若隐若现的山腰） */
    .mountain-mid {
        position: absolute;
        left: 0;
        right: 0;
        bottom: 0;
        height: 42%;
        z-index: 2;
        background: linear-gradient(180deg, rgba(45, 45, 45, 0.12), rgba(45, 45, 45, 0.26));
        clip-path: polygon(0 66%, 8% 40%, 16% 60%, 26% 26%, 36% 54%, 46% 18%, 56% 48%, 66% 28%, 76% 56%, 86% 34%, 95% 54%, 100% 44%, 100% 100%, 0 100%);
        pointer-events: none;
        animation: riseUp 1.15s ease 0.2s both;
    }

    /* 近山（浓墨剪影，山脚再压一层湿墨） */
    .mountain-near {
        position: absolute;
        left: 0;
        right: 0;
        bottom: 0;
        height: 36%;
        z-index: 3;
        background:
            linear-gradient(180deg, rgba(20, 20, 20, 0) 0%, rgba(20, 20, 20, 0.34) 78%, rgba(16, 16, 16, 0.5) 100%),
            linear-gradient(180deg, rgba(30, 30, 30, 0.34), rgba(26, 26, 26, 0.58));
        clip-path: polygon(0 60%, 10% 36%, 21% 54%, 33% 20%, 45% 50%, 57% 28%, 69% 56%, 81% 38%, 93% 58%, 100% 44%, 100% 100%, 0 100%);
        pointer-events: none;
        animation: riseUp 1.2s ease 0.3s both;
    }

    @keyframes riseUp {
        from { transform: translateY(100%); opacity: 0.35; }
        to   { transform: translateY(0);    opacity: 1; }
    }

    /* 山脚水雾（底部淡色雾带） */
    .water-band {
        position: absolute;
        left: 0;
        right: 0;
        bottom: 0;
        height: 5rem;
        z-index: 4;
        background: linear-gradient(180deg, rgba(245, 240, 230, 0) 0%, rgba(240, 234, 220, 0.55) 55%, rgba(233, 225, 208, 0.8) 100%);
        filter: blur(5px);
        pointer-events: none;
        animation: fadeIn 1.4s ease 0.5s both;
    }

    /* 飘动云雾（慢速横向漂移） */
    .mist {
        position: absolute;
        border-radius: 50%;
        background: radial-gradient(ellipse at center, rgba(250, 248, 245, 0.75), rgba(250, 248, 245, 0) 70%);
        filter: blur(22px);
        pointer-events: none;
        z-index: 6;
        animation: mistDrift 30s ease-in-out infinite alternate;
    }
    .mist-a { width: 72vw; height: 26vh; left: -14vw; top: 16%; }
    .mist-b { width: 56vw; height: 20vh; right: -10vw; top: 30%; animation-delay: -14s; }

    @keyframes mistDrift {
        from { transform: translateX(-4%); opacity: 0.45; }
        to   { transform: translateX(5%);  opacity: 0.85; }
    }

    /* 左侧竖排题字（不对称构图） */
    .side-inscription {
        position: absolute;
        left: 2.4rem;
        top: 50%;
        transform: translateY(-50%);
        writing-mode: vertical-rl;
        font-family: var(--font-call) !important;
        font-size: 1.45rem;
        line-height: 2.1;
        letter-spacing: 0.32em;
        text-align: center;
        color: rgba(45, 45, 45, 0.3);
        pointer-events: none;
        z-index: 7;
        animation: fadeIn 1.4s ease 0.9s both;
    }

    /* 右上题跋（落日旁的竖排诗句） */
    .colophon {
        position: absolute;
        right: 15%;
        top: 30%;
        writing-mode: vertical-rl;
        font-family: var(--font-call) !important;
        font-size: 1rem;
        line-height: 2.5;
        letter-spacing: 0.28em;
        text-align: center;
        color: rgba(45, 45, 45, 0.36);
        pointer-events: none;
        z-index: 7;
        animation: fadeIn 1.4s ease 1.05s both;
    }

    /* 宣纸颗粒（feTurbulence 噪声，5% 乘叠在最上层营造纸纹） */
    .paper-grain {
        position: absolute;
        inset: 0;
        z-index: 9;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='240'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.6'/%3E%3C/svg%3E");
        background-size: 240px 240px;
        opacity: 0.05;
        mix-blend-mode: multiply;
        pointer-events: none;
    }

    @keyframes fadeIn {
        from { opacity: 0; }
        to   { opacity: 1; }
    }

    /* 居中主内容：唯一正常流元素（被 .start-screen 的 flex 双向居中），
       压在绝对定位背景层之上 */
    .start-content {
        position: relative;
        z-index: 8;
    }

    /* 印章「盖章」入场：放大砸下再回弹（呼应画上落款的仪式感） */
    @keyframes sealStamp {
        0%   { transform: rotate(-4deg) scale(2.6); opacity: 0; }
        55%  { transform: rotate(-8deg) scale(0.9); opacity: 1; }
        72%  { transform: rotate(-3deg) scale(1.08); opacity: 1; }
        100% { transform: rotate(-4deg) scale(1);    opacity: 1; }
    }

    /* 开始界面「开始对话」按钮容器居中（2026-09-03 修复，streamlit 1.63）：
       Streamlit 1.63 起 st.button 被包进 shrink-wrap 的 stElementContainer
       （带 st-key-<key> 类），容器收缩成按钮自身宽度、内部 margin:auto 没有
       剩余空间可分，按钮在 3/5 列内被上层 flex justify:start 左对齐（实测
       1280 视口偏左 86px）。强制该容器全宽 + flex 居中即回正中心。
       key 对应 app.py 的 st.button(key="start_enter")；1.32 无此容器层，
       该选择器不匹配、无副作用。 */
    .st-key-start_enter {
        display: flex !important;
        justify-content: center !important;
        width: 100% !important;
    }

    /* 主按钮（st.button type="primary" → kind="primary"）：
       大号金边药丸，仅用于开始界面「开始对话」。
       display:block + margin:auto 让胶囊在列内自身居中（streamlit 容器默认
       不居中；1.63 由上方 .st-key-start_enter 容器规则负责水平居中，
       此处的 auto 边距与之配合不冲突），故调用处不用 use_container_width。
       入场动画随整页交错编排。 */
    .stButton button[kind="primary"] {
        font-family: var(--font-label) !important;
        font-size: 1.2rem !important;
        letter-spacing: 0.35em;
        padding: 0.85rem 2.2rem !important;
        border-radius: 999px !important;
        display: block;
        width: auto !important;
        min-width: 15rem;
        margin: 0.6rem auto 2rem;
        background: linear-gradient(135deg, rgba(184, 134, 11, 0.32) 0%, rgba(184, 134, 11, 0.12) 100%) !important;
        border: 1px solid var(--gold) !important;
        color: var(--gold) !important;
        box-shadow: 0 4px 18px rgba(184, 134, 11, 0.25);
        transition: all 0.3s ease !important;
        position: relative;
        overflow: hidden;
        animation: fadeInUp 0.85s ease 1.35s both;
    }

    /* 悬停时一道金光从左扫过（笔意） */
    .stButton button[kind="primary"]::after {
        content: '';
        position: absolute;
        top: 0;
        left: -130%;
        width: 55%;
        height: 100%;
        background: linear-gradient(115deg, transparent, rgba(250, 248, 245, 0.4), transparent);
        transform: skewX(-20deg);
        transition: left 0.65s ease;
        pointer-events: none;
    }
    .stButton button[kind="primary"]:hover::after {
        left: 150%;
    }

    .stButton button[kind="primary"]:hover {
        background: linear-gradient(135deg, rgba(184, 134, 11, 0.45) 0%, rgba(184, 134, 11, 0.22) 100%) !important;
        transform: translateY(-2px);
        box-shadow: 0 8px 28px rgba(184, 134, 11, 0.35);
        border-color: var(--gold-light) !important;
    }

    /* ========== 人物信息卡片 ========== */
    .character-profile {
        display: flex;
        gap: 2rem;
        padding: 1.8rem 2rem;
        background: linear-gradient(135deg, var(--paper-light) 0%, var(--paper) 100%);
        border: 1px solid rgba(184, 134, 11, 0.2);
        border-radius: 16px;
        margin-bottom: 1.4rem;
        position: relative;
        overflow: hidden;
        animation: slideIn 0.5s ease;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
    }

    @keyframes slideIn {
        from { opacity: 0; transform: translateY(-18px); }
        to   { opacity: 1; transform: translateY(0); }
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
        min-width: 170px;
        flex-shrink: 0;
    }

    .profile-avatar {
        font-size: 4.6rem;
        filter: drop-shadow(0 8px 16px rgba(0, 0, 0, 0.15));
        animation: float 3s ease-in-out infinite;
        line-height: 1.1;
    }

    @keyframes float {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-9px); }
    }

    .profile-name {
        font-family: var(--font-call);
        font-size: 2.3rem;
        color: var(--gold);
        margin-top: 0.4rem;
        text-shadow: 0 2px 10px rgba(184, 134, 11, 0.2);
        line-height: 1.2;
    }

    .profile-title {
        font-size: 0.95rem;
        color: var(--ink-soft);
        margin-top: 0.25rem;
    }

    .profile-meta {
        display: flex;
        gap: 1.4rem;
        margin-top: 0.9rem;
        justify-content: center;
    }

    .meta-item {
        font-size: 0.82rem;
        color: var(--ink-soft);
    }

    .meta-item strong {
        color: var(--gold);
    }

    .profile-info-section {
        flex: 1;
        min-width: 0;
    }

    .info-section-title {
        font-family: var(--font-label);
        font-size: 1.15rem;
        font-weight: 400;
        color: var(--gold);
        margin-bottom: 0.7rem;
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
        line-height: 1.85;
        font-size: 0.94rem;
        max-height: 13rem;
        overflow: hidden auto;
        padding-right: 0.5rem;
    }

    .quote-container {
        margin-top: 1.2rem;
        padding: 0.9rem 1rem;
        background: rgba(184, 134, 11, 0.05);
        border-left: 3px solid var(--gold);
        border-radius: 0 8px 8px 0;
    }

    .quote-text {
        font-style: italic;
        color: rgba(45, 45, 45, 0.72);
        font-size: 0.88rem;
        line-height: 1.6;
        margin: 0 0 0.3rem;
    }

    .quote-text:last-child {
        margin-bottom: 0;
    }

    .quote-text::before {
        content: '"';
        font-size: 1.5rem;
        color: var(--gold);
        margin-right: 0.3rem;
        line-height: 0;
    }

    /* ========== 对话消息 ========== */
    .stChatMessage {
        background: transparent !important;
        padding: 0.4rem 0 !important;
        margin-bottom: 0.6rem !important;
    }

    .stChatMessage[data-testid="user-message"] {
        background: transparent !important;
    }

    .stChatMessage[data-testid="assistant-message"] {
        background: transparent !important;
    }

    /* 消息主体气泡 */
    .stChatMessage .stChatMessageContent {
        background: linear-gradient(135deg, rgba(184, 134, 11, 0.07) 0%, rgba(184, 134, 11, 0.02) 100%);
        border: 1px solid rgba(184, 134, 11, 0.18);
        border-radius: 4px 14px 14px 14px;
        padding: 0.7rem 1.1rem;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
        max-width: 860px;
    }

    .stChatMessage[data-testid="user-message"] .stChatMessageContent {
        background: linear-gradient(135deg, rgba(90, 143, 123, 0.1) 0%, rgba(90, 143, 123, 0.04) 100%);
        border: 1px solid rgba(90, 143, 123, 0.25);
        border-radius: 14px 4px 14px 14px;
        max-width: 780px;
        margin-left: auto;
    }

    .stChatMessage p {
        color: var(--ink-dark) !important;
        line-height: 1.85 !important;
        font-size: 0.98rem;
    }

    /* 头像 */
    .stChatMessage [data-testid="stChatMessageAvatar"] {
        width: 42px;
        height: 42px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        background: rgba(184, 134, 11, 0.12) !important;
        border: 1px solid rgba(184, 134, 11, 0.3);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        flex-shrink: 0;
        line-height: 1;
    }

    .stChatMessage[data-testid="user-message"] [data-testid="stChatMessageAvatar"] {
        background: rgba(90, 143, 123, 0.14) !important;
        border-color: rgba(90, 143, 123, 0.35);
    }

    /* 回复头部（角色名 + 称号朝代） */
    .chat-author {
        display: flex;
        align-items: baseline;
        gap: 0.55rem;
        margin-bottom: 0.3rem;
    }

    .chat-author-name {
        font-family: var(--font-label);
        font-size: 1.08rem;
        color: var(--gold);
        letter-spacing: 0.08em;
    }

    .chat-author-meta {
        font-size: 0.72rem;
        color: var(--ink-faint);
        letter-spacing: 0.05em;
    }

    /* 消息内「参考史料」可折叠面板 */
    .stChatMessage .stExpander {
        border: none !important;
        background: transparent !important;
        margin-top: 0.4rem !important;
        margin-bottom: 0 !important;
        box-shadow: none !important;
    }

    .stChatMessage .stExpander summary {
        padding: 0.25rem 0 !important;
        background: transparent !important;
        font-family: var(--font-body) !important;
        font-size: 0.78rem !important;
        color: var(--jade) !important;
        letter-spacing: 0.05em;
    }

    .stChatMessage .stExpander summary:hover {
        background: transparent !important;
        color: var(--gold) !important;
    }

    .stChatMessage .stExpander summary p {
        color: var(--jade) !important;
    }

    .stChatMessage .stExpander [data-testid="stExpanderDetails"] {
        border-top: 1px dashed rgba(90, 143, 123, 0.3);
        padding-top: 0.3rem;
    }

    /* 溯源条目 */
    .src-item {
        display: flex;
        gap: 0.6rem;
        padding: 0.35rem 0;
        align-items: flex-start;
    }

    .src-item + .src-item {
        border-top: 1px dashed rgba(90, 143, 123, 0.16);
    }

    .src-idx {
        font-family: var(--font-label);
        color: var(--gold);
        font-size: 0.8rem;
        min-width: 1.2rem;
        text-align: center;
        line-height: 1.7;
        margin-top: 0.05rem;
    }

    .src-body {
        font-size: 0.85rem;
        line-height: 1.65;
        color: var(--ink-medium);
        min-width: 0;
    }

    .src-link {
        color: var(--ink-dark);
        text-decoration: none;
        font-weight: 600;
    }

    a.src-link:hover {
        color: var(--gold);
        text-decoration: underline;
    }

    .src-attr {
        display: block;
        font-size: 0.72rem;
        color: var(--ink-faint);
        font-style: italic;
    }

    /* 输入框 */
    .stChatInput {
        border: 1px solid rgba(184, 134, 11, 0.3) !important;
        border-radius: 12px !important;
        background: var(--paper) !important;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.04);
    }

    .stChatInput:focus-within {
        border-color: var(--gold) !important;
        box-shadow: 0 0 0 1px rgba(184, 134, 11, 0.25), 0 4px 18px rgba(184, 134, 11, 0.08) !important;
    }

    .stChatInput textarea {
        background: transparent !important;
        color: var(--ink-dark) !important;
        font-family: var(--font-body) !important;
    }

    .stChatInput textarea::placeholder {
        color: var(--ink-faint) !important;
    }

    /* 底部操作条 */
    .chat-actions {
        margin-top: 0.8rem;
    }

    /* 分隔线 */
    .divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(184, 134, 11, 0.3), transparent);
        margin: 1.6rem 0;
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
        opacity: 0.04;
        background-image:
            radial-gradient(ellipse at 18% 26%, rgba(184, 134, 11, 0.3) 0%, transparent 50%),
            radial-gradient(ellipse at 82% 72%, rgba(90, 143, 123, 0.22) 0%, transparent 50%),
            radial-gradient(ellipse at 55% 45%, rgba(199, 62, 58, 0.1) 0%, transparent 70%);
    }

    /* 滚动条 */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
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

    /* ========== 窄屏适配 ========== */
    @media (max-width: 960px) {
        .character-profile {
            flex-direction: column;
            gap: 1.2rem;
        }

        .profile-avatar-section {
            min-width: 0;
        }

        .welcome-title {
            font-size: 2.6rem !important;
        }

        .hero-stats {
            gap: 2rem;
        }

        .start-screen {
            min-height: calc(100vh - 12rem);
        }

        .ink-sun {
            width: 72px;
            height: 72px;
            right: 8%;
        }

        .hero-seal {
            width: 60px;
            height: 60px;
            padding: 6px;
        }

        .hero-seal span {
            font-size: 1.05rem;
        }

        /* 小屏收起两侧题跋与云雾，避免与主内容拥挤 */
        .side-inscription,
        .colophon,
        .mist-a,
        .mist-b {
            display: none;
        }
    }

    @media (max-width: 700px) {
        .stChatMessage .stChatMessageContent,
        .stChatMessage[data-testid="user-message"] .stChatMessageContent {
            max-width: 100%;
            margin-left: 0;
        }
    }
</style>
"""
