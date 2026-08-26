# 历史人物对话 Agent — 项目完整说明

> 基于 **LangChain + RAG** 的沉浸式历史人物对话系统，支持与中国历史人物进行角色扮演式、可溯源的多轮对话。

| 版本 | 说明 |
|------|------|
| 文档状态 | 2026-08-14 依据当前代码库编写 |
| 代码位置 | `/home/tjut_lixiang/web-learning/agent/agent-make` |
| 项目性质 | 学习复现 + 工程化改造的完整 Agent 项目（fork 自 `dreamlee0/history-rag-chat`） |

---

## 一、产品简介

本产品是一个"**与历史人物对话**"的 Web 应用：用户可以从 97 位覆盖上古至民国的历史人物中任选一位，以自然语言与其沉浸式对话。

- 人物不是简单的"套皮聊天"，而是由 **人物档案（YAML）+ 史料知识库（RAG）** 双重驱动的真实还原；
- 回答基于真实史料检索增强生成，**带知识溯源**（显示参考史料），并内置多条**防幻觉规则**；
- 支持**多轮上下文记忆、SQLite 持久化、对话导出**，刷新/重开页面不丢失；
- 提供**水墨丹青风格的 Streamlit 界面**，并可一键部署到 Streamlit Cloud 供在线体验。

**一句话定位**：一个具备"人物角色 + 史料问答 + 知识溯源 + 持久化 + 工程健壮性"的完整生产级历史人物 RAG Agent。

---

## 二、核心功能

### 2.1 角色扮演
- **97 位历史人物**，覆盖上古、商、周、春秋战国、秦汉、三国、唐、宋、元、明、清、民国等 **20 个朝代**；
- 每位人物由独立的 YAML 档案定义（身份、生卒年、性格、说话风格、知识领域、名言），系统提示词据此生成，人物口吻与时代感真实还原。

### 2.2 RAG 知识增强与溯源
- 内置 **99 篇史料文档**（97 篇人物传记 + 官渡之战、赤壁之战 2 篇事件史料），由本地向量库检索增强生成；
- 每条回答末尾自动标注【参考史料】，支持**知识溯源**；
- 检索采用"按人物过滤优先 + 全局兜底"策略，避免跨人物史料污染（详见 4.3）。

### 2.3 多轮对话与记忆
- 内存对话记忆（最近 10 轮）+ SQLite 持久化双层结构；
- 记忆按 **"会话:人物"复合键** 隔离，多用户、多人物之间互不串扰。

### 2.4 对话持久化与管理
- SQLite（WAL 模式）存储对话与会话消息，刷新页面、切换人物、重开应用均不丢失；
- 支持历史对话列表、继续对话、删除对话。

### 2.5 对话导出
- 支持将对话导出为 **Markdown / PDF** 格式下载。

### 2.6 Web 界面
- Streamlit 构建，**水墨丹青**风格：人物选择（按朝代折叠）、人物档案展示、聊天界面、最近对话/推荐人物；
- 移动端与云端均可运行。

### 2.7 知识库工具链
- 提供史料**爬虫**（`crawl_knowledge.py`，项目唯一爬虫）、**知识生成**（`generate_knowledge.py`）与**向量库构建**（`build_vector_db.py`）脚本，支持知识库扩展。

### 2.8 工程化与测试
- 22 个 pytest 用例（人物加载、知识库完整性、RAG 检索防污染、防幻觉提示词、记忆隔离等）；
- Dev Container + Streamlit Cloud 部署支持。

---

## 三、亮点特色

### 3.1 产品级亮点
- **历史还原与防幻觉并重**：不只"像"，更求"准"——史料明确记载的照实回答，未记载的如实说明"史料记载有限"，绝不编造年份、数字或文献出处；
- **零 API 幻觉成本**：LLM 使用免费额度的 `glm-4.5-flash`，Embedding 使用**本地 HuggingFace 模型**（`BAAI/bge-small-zh-v1.5`），无需额外 API Key；
- **跨人物问答不串味**：向李白问杜甫，系统能识别"与本人物无关"并退回全局检索，不会把李白自己的传记误当"杜甫史料"注入（实测同人距离比 ~1.0、跨人 ~1.83）；
- **开箱即用的知识库**：向量库已构建并随仓库提交，首次启动无需联网下载模型即可使用（本地缓存模型时）。

### 3.2 工程级亮点
- **版本严格钉死**（如 `chromadb==1.5.8`、`langchain==1.2.15`），与向量库构建环境一致，规避 0.x/1.x 格式不兼容；
- **云端部署兼容**：Streamlit Secrets 自动桥接为环境变量，解决云端 `LLM_API_KEY` 读取问题；
- **健壮的 API 调用**：超时控制、指数退避重试、用户友好的错误提示（区分网络/密钥/通用错误）；
- **Embedding 离线加载优化**：自动解析本地模型快照，避免联网校验挂起数十秒甚至 >200s（详见 4.4）。

---

## 四、技术方案与架构

### 4.1 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                       Streamlit Web 界面                     │
│          （水墨丹青样式 / 人物选择 / 对话 / 导出）             │
└───────────────────────────┬─────────────────────────────────┘
                            │
                 ┌──────────▼──────────┐
                 │   HistoryCharacterAgent  │  ← 核心编排层
                 │   (src/agents/history_agent.py)             │
                 └───┬──────────┬──────────┬────┘
                     │          │          │
        ┌────────────▼───┐  ┌───▼──────┐  ┌▼──────────────────┐
        │  RAG 检索层     │  │ 记忆层     │  │ 持久化层           │
        │ VectorStore     │  │ Conversation│  │ SQLite Database   │
        │ (Chroma + bge)  │  │ Memory     │  │ (conversations/   │
        │ 人物过滤/全局   │  │ 会话:人物  │  │  messages 表)      │
        └────────┬────────┘  └────┬──────┘  └────────┬──────────┘
                 │                │                  │
        ┌────────▼────────┐  ┌───▼──────┐   ┌───────▼─────────┐
        │ 数据层           │  │ 配置层     │   │ 工具链           │
        │ data/knowledge  │  │ config/    │   │ scripts/(爬虫/  │
        │ (99篇史料)      │  │ settings   │   │ 构建向量库/生成) │
        │ data/characters │  │ (.env/     │   │ tests/(22用例)  │
        │ (97位YAML)      │  │ Secrets)   │   │                 │
        └─────────────────┘  └───────────┘   └─────────────────┘
```

### 4.2 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| Agent 框架 | LangChain (`1.2.x`) | 文档处理、向量存储、消息封装 |
| 大语言模型 | 智谱 AI `glm-4.5-flash`（OpenAI 兼容） | 免费方案，可换 DeepSeek/OpenAI 等 |
| Embedding | 本地 `BAAI/bge-small-zh-v1.5` (HuggingFace) | 本地运行，免费、无需 API Key |
| 向量数据库 | Chroma (`1.5.8`) | `data/vector_db`，含人物/分类元数据过滤 |
| 对话存储 | SQLite (WAL) | 轻量实现，无 ORM 依赖 |
| Web 界面 | Streamlit | 水墨丹青 CSS 定制 |
| 配置管理 | pydantic-settings + .env / Secrets | 环境变量优先 |
| 导出 | reportlab (PDF) / Markdown | |

### 4.3 对话 / RAG 检索流程

1. **选择人物** → 加载 YAML 档案，生成人物系统提示词（身份、性格、说话风格、知识领域、名言）；
2. **用户输入** → 若为新对话则创建 conversation 记录；
3. **记忆恢复**：按 `会话:人物` 复合键读取内存记忆，空则从 SQLite 恢复最近 10 轮；
4. **RAG 检索**（核心逻辑，`_retrieve_knowledge`）：
   - ① 按人物过滤检索（带距离分数）；
   - ② 全局检索（带距离分数）；
   - ③ 若过滤最优结果明显劣于全局最优（`过滤得分 > 全局最优 × 1.25`）→ 判定问题与本人物无关，**退回全局检索**；
   - ④ 将命中史料拼装为上下文，生成溯源列表；
5. **组装消息** → System Prompt（人物设定 + 史料 + 4 条硬性防幻觉规则/引用格式） + 历史消息 + 当前问题；
6. **调用 LLM**（超时 + 指数退避重试，区分错误类型提示）→ 得到回复；
7. **持久化**：助手消息连同引用来源 JSON 一并写入 SQLite，并更新内存记忆；
8. **前端展示**回复内容 + 参考资料，支持导出/清空/更换人物。

### 4.4 关键技术特色与设计决策

#### ① 检索相关性阈值，杜绝跨人物史料污染（`FILTERED_SCORE_RATIO = 1.25`）
按人物过滤检索的语义距离若明显劣于全局最优，说明问题与本人物无关，自动退回全局检索。
**解决的问题**：向李白问"杜甫的诗"，原本会命中李白自己的传记（自传在"李白"过滤下必然得分最高），被当作"相关史料"注入导致引用错误。
**实测效果**：同人检索距离比 ~1.0，跨人 ~1.83，阈值可清晰区分。对应测试见 `tests/test_retrieval.py`。

#### ② 会话记忆复合键 `session_id:character_name`
内存记忆与数据库归属均以"会话+人物"双重维度隔离，多用户、多角色不串记。对应测试见 `tests/test_memory.py`。

#### ③ Embedding 离线加载（`_resolve_embedding_model`）
新版 `huggingface_hub` 的 `hf_hub_download` 默认 `local_files_only=False`，会**忽略 `HF_HUB_OFFLINE` 环境变量**并强制联网校验，在受限网络下可挂起 >200s。
本项目自动把模型解析为**本地缓存快照路径**后加载（约 5s），并顺带启用离线环境变量；本地无缓存时（如云端首次部署）则退回正常下载。对应测试见 `tests/conftest.py`。

#### ④ 系统提示词 4 条硬性防幻觉规则
- 以史料为准，不增删虚构细节；
- 史料未记载的明确说明，不编造史实/年份/数字/文献；
- 引用仅限检索到的史料列表；
- 保持人物口吻但事实必须准确。
无 RAG 命中时进入专门分支："基于可靠常识 + 切勿编造出处/数字"。对应测试见 `tests/test_agent_prompt.py`。

#### ⑤ 低成本部署方案
LLM 用 `glm-4.5-flash`（免费/低费）+ Embedding 本地化（零 API 成本）+ 向量库随仓库提交（免首次构建），实现"近乎零成本运行 + 云端可部署"。

#### ⑥ 版本钉死与兼容性
`requirements.txt` 明确标注各关键包必须版本（尤其 `chromadb==1.5.8` 不可降到 0.x，与已提交向量库格式匹配），并说明与构建环境一致，避免线上/线下格式不兼容。

---

## 五、目录结构

```
agent-make/
├── config/
│   └── settings.py            # pydantic-settings 配置（LLM/Embedding/向量库/DB）
├── data/
│   ├── characters/            # 97 位历史人物配置（按朝代分目录，YAML）
│   ├── knowledge/             # 史料知识库（99 篇：97 传记 + 2 事件）
│   │   ├── biography_*.txt    # 人物传记（头部含 来源/分类/人物 元数据）
│   │   ├── event_*.txt        # 事件史料
│   │   └── crawl_cache.json   # 爬虫缓存
│   ├── vector_db/             # Chroma 向量数据库（已构建并提交）
│   └── history_chat.db        # SQLite 对话库（运行生成）
├── scripts/                   # 工具脚本
│   ├── build_vector_db.py     # 构建向量库
│   ├── crawl_knowledge.py     # 史料爬虫（唯一爬虫，带请求头/重试/缓存）
│   └── generate_knowledge.py  # 知识生成（仅初始内置知识，已提交文件为准）
├── src/
│   ├── agents/history_agent.py        # 核心 Agent（RAG 检索 + 提示词 + 对话编排）
│   ├── characters/character_manager.py# 人物加载/朝代分组/系统提示词生成
│   ├── database/db.py                 # SQLite CRUD（会话/消息/统计/搜索）
│   ├── memory/conversation_memory.py  # 内存记忆（deque + 复合键）
│   └── retrievers/vector_store.py     # Chroma 管理 + Embedding 离线加载 + 文档加载
├── web/
│   ├── app.py                 # Streamlit 主应用（Secrets 桥接/界面/会话）
│   ├── styles.py              # 水墨丹青 CSS
│   └── export_utils.py        # Markdown/PDF 导出
├── tests/                     # 22 个 pytest 用例（5 个测试模块）
├── images/                    # 项目截图
├── .devcontainer/             # Dev Container 开发环境
├── .streamlit/config.toml     # Streamlit 服务器配置
├── run.sh                     # 启动脚本
├── packages.txt               # 系统级字体（fonts-wqy-zenhei，中文显示）
└── requirements.txt           # Python 依赖（版本钉死）
```

---

## 六、数据说明

| 数据 | 数量 | 说明 |
|------|------|------|
| 历史人物 | 97 位 | 覆盖 20 个朝代，每人一个 YAML 档案 |
| 史料文档 | 99 篇 | 97 篇人物传记 + 2 篇事件史料（官渡、赤壁） |
| 向量库块数 | 按文本分割自动生成 | 500 字/块、100 字重叠，中文标点分隔 |
| 数据库表 | 2 张 | `conversations`（会话）+ `messages`（消息，含 sources_json 溯源） |

史料文档头部约定元数据格式（`load_knowledge_files` 解析）：
```
# 标题
【来源】来源名称
【URL】链接
【分类】biography / event
【人物】对应人物
---
正文内容
```

---

## 七、快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY（智谱 AI 或任意 OpenAI 兼容 Key）

# 3. 启动应用
streamlit run web/app.py
# 或 ./run.sh
```

本地访问 `http://localhost:8501`。

> 说明：
> - 若本地已缓存 Embedding 模型（`~/.cache/huggingface`），启动即用，无需联网下载；
> - 若向量库为空，先运行 `python scripts/build_vector_db.py`（或首次启动时应用自动构建）；
> - 云端（Streamlit Cloud）：在 Secrets 中配置 `LLM_API_KEY` 等，应用会自动桥接为环境变量。

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | LLM API Key | - |
| `LLM_BASE_URL` | LLM 接口地址 | `https://open.bigmodel.cn/api/paas/v4` |
| `LLM_MODEL` | 大模型名称 | `glm-4.5-flash` |
| `EMBEDDING_MODEL` | 本地 Embedding 模型 | `BAAI/bge-small-zh-v1.5` |
| `VECTOR_DB_PATH` | 向量库路径 | `./data/vector_db` |
| `DB_PATH` | 对话库路径 | `./data/history_chat.db` |
| `APP_TITLE` | 应用标题 | 历史人物对话 |

---

## 八、测试

22 个用例，覆盖 5 个维度：

| 模块 | 覆盖内容 |
|------|----------|
| `test_characters.py` | 人物加载、必填字段、朝代顺序、人物与知识文件一一对应、重名检查 |
| `test_knowledge.py` | 知识文件加载、元数据完整性、史实正确性抽查（如隋文帝无大运河、隋炀帝有大运河） |
| `test_retrieval.py` | 同人检索保持人物聚焦、跨人检索退回全局、**不注入当事人传记**、人物自有知识可检索 |
| `test_memory.py` | 复合键含人物、同人物跨会话隔离、复合键清空 |
| `test_agent_prompt.py` | 防幻觉规则存在、引用限于检索来源、无 RAG 分支禁止编造、角色与事实平衡 |

```bash
pytest tests/ -v
```

> 注：无本地 Embedding 缓存的机器会自动跳过需要 embedding 的检索类测试（见 `tests/conftest.py`）。

---

## 九、局限与展望

**当前局限**
- 知识库为内置百科式传记，深度有限（每篇人物约 1~2 千字），对冷门细节覆盖不足；
- 人物配置（97 位）与知识文档（99 篇）由脚本/内置数据生成，尚未覆盖全部正史细节；
- LLM 依赖外部 API（需联网），本地仅 Embedding 离线。

**可扩展方向**
- 扩充史料来源（爬虫已具备基础，可接入百科/正史多源并清洗）；
- 增加"朝代背景"等全局知识文档，提升跨人物问答质量；
- 引入流式输出、引用高亮交互、多模态人物头像；
- 将检索策略升级为多路召回 + 重排（Rerank）；
- 接入 Agent 工具调用（时间线、事件检索、诗作生成）增强能力边界。

---

## 十、License

MIT License（详见仓库 LICENSE）。
