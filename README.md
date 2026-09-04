# 🏛️ 历史人物对话系统（history-rag-chat）

[English](README.en.md) | 中文

> 基于 **LangChain + RAG** 的历史人物对话系统：与中国历史人物进行沉浸式、可溯源的多轮对话。

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![LangChain](https://img.shields.io/badge/LangChain-1.2-green.svg)](https://langchain.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📸 项目预览

### 🖥️ 开始界面

<div align="center">
  <img src="images/开始.png" alt="开始" width="800"/>
</div>

### 🎭 人物选择界面

<div align="center">
  <img src="images/chat界面.png" alt="人物选择界面" width="800"/>
</div>

### 💬 对话展示界面

<div align="center">
  <img src="images/对话展示.png" alt="对话展示界面" width="800"/>
</div>

<div align="center">
  <img src="images/人物选择.png" alt="聊天界面" width="800"/>
</div>

## ✨ 功能特点

- 🎭 **角色扮演** · 97 位历史人物，覆盖 21 个朝代（三国拆蜀汉/东吴/曹魏），真实还原人物性格与口吻
- 📚 **RAG 知识增强** · 基于真实史料回答，知识可溯源、引用可验证
- 🔎 **混合检索** · 可选 `retrieval_mode=hybrid`（稠密向量 × BM25 词法 RRF 融合召回，离线可跑），提升精确人名/多人物枚举召回
- 📄 **多格式文档** · 知识库支持 txt / md / html / pdf / docx / xml / json / csv / tsv / xlsx 统一解析入库
- 💬 **多轮对话记忆** · SQLite 持久化，刷新不丢失
- 📤 **对话导出** · Markdown / PDF
- 📏 **内置评测体系** · 标注评测集 + hit@k / MRR / 阈值标定 + 分阶段延迟/成本剖析 + Mock 端到端评测，防跨人物污染可量化

## 🚀 快速开始

在线体验：[history-rag-chat.streamlit.app](https://history-rag-chat.streamlit.app/)

```bash
git clone https://github.com/dreamlee0/history-rag-chat.git
cd history-rag-chat
pip install -r requirements.txt
cp .env.example .env          # 填入 LLM_API_KEY（DeepSeek 或任意 OpenAI 兼容接口）
streamlit run web/app.py
```

## 🧩 技术栈

| 组件 | 说明 |
|---|---|
| LangChain + Chroma | RAG 检索增强 |
| DeepSeek deepseek-v4-flash | LLM（OpenAI 兼容） |
| BAAI/bge-small-zh-v1.5 | 本地 Embedding（免费，无需 Key） |
| SQLite + Streamlit | 持久化 / Web 界面 |

## 📁 项目结构

```
history-rag-chat/
├── config/                  # 配置管理
│   └── settings.py
├── data/
│   ├── characters/          # 97位历史人物配置（YAML）
│   │   ├── shanggu/         # 上古
│   │   ├── shang/           # 商朝
│   │   ├── xizhou/          # 西周
│   │   ├── chunqiu/         # 春秋
│   │   ├── zhanguo/         # 战国
│   │   ├── qin/             # 秦朝
│   │   ├── xihan/           # 西汉
│   │   ├── donghan/         # 东汉末
│   │   ├── sanguo/          # 三国
│   │   ├── dongjin/         # 东晋
│   │   ├── sui/             # 隋朝
│   │   ├── tang/            # 唐朝
│   │   ├── beisong/         # 北宋
│   │   ├── nansong/         # 南宋
│   │   ├── yuan/            # 元朝
│   │   ├── ming/            # 明朝
│   │   ├── qing/            # 清朝
│   │   ├── wudai/           # 五代十国
│   │   └── minguo/          # 民国
│   ├── knowledge/           # 史料知识库（双轨：99 persona + 107 真实史源〔81 gushiwen 原文 + 21 百度百科 + 5 ctext〕，支持多格式）
│   ├── documents_sample/    # 多格式解析样例语料（md/html/json/csv）
│   ├── eval/                # 标注评测集
│   └── vector_db/           # Chroma向量数据库
├── scripts/                 # 工具脚本（评测/延迟/端到端/摄取/清理）
├── src/
│   ├── agents/              # 对话编排 / RAG 检索（含混合检索路径与 llm_backend 注入）
│   ├── characters/          # 人物管理器
│   ├── database/            # SQLite数据库
│   ├── memory/              # 对话记忆
│   └── retrievers/          # 向量检索 / BM25 词法索引 / 多格式文档解析
├── web/
│   ├── app.py               # 主应用
│   ├── styles.py            # 水墨丹青样式
│   └── export_utils.py      # 导出工具
├── images/                  # 项目截图
└── requirements.txt
```

## 📚 历史人物列表（97 位）

| 朝代 | 人物 |
|------|------|
| **上古** | 黄帝、炎帝、尧、舜、禹 |
| **商朝** | 商汤 |
| **西周** | 周文王、周武王、周公、姜子牙 |
| **春秋** | 老子、孔子、孙武、墨子、范蠡 |
| **战国** | 商鞅、屈原、蔺相如、白起 |
| **秦朝** | 秦始皇、李斯、蒙恬 |
| **西汉** | 刘邦、张良、韩信、萧何、卫青、霍去病、张骞、司马迁、汉武帝 |
| **东汉末** | 曹操 |
| **三国** | 刘备、关羽、张飞、赵云、周瑜、孙权、司马懿、诸葛亮 |
| **东晋** | 王羲之、陶渊明 |
| **隋朝** | 隋文帝、隋炀帝 |
| **唐朝** | 唐太宗、武则天、李白、杜甫、白居易、王维、韩愈、颜真卿、玄奘、李商隐、杜牧 |
| **北宋** | 赵匡胤、范仲淹、欧阳修、王安石、司马光、苏轼 |
| **南宋** | 辛弃疾、陆游、文天祥、岳飞 |
| **元朝** | 成吉思汗、忽必烈、关汉卿 |
| **明朝** | 朱元璋、朱棣、郑和、于谦、海瑞、戚继光、李时珍、徐霞客、王阳明、张居正 |
| **清朝** | 康熙、雍正、乾隆、纪晓岚、和珅、林则徐、曾国藩、左宗棠、李鸿章、张之洞、曹雪芹、郑板桥、慈禧 |
| **五代十国** | 李煜、柴荣 |
| **民国** | 孙中山、鲁迅、蔡元培、梁启超 |

## 💡 使用示例

```
# 与李白对话
用户：李白先生，您最著名的诗作是哪首？
李白：哈哈哈哈！老夫平生诗作无数，若说最得意之作，当属《将进酒》！

# 与诸葛亮对话
用户：诸葛亮先生，您觉得北伐能成功吗？
诸葛亮：北伐之事，亮已深思熟虑。虽知其难，然兴复汉室乃先帝遗志...

# 与孔子对话
用户：孔子先生，如何才能成为君子？
孔子：君子之道，在于修身齐家治国平天下。首在修身...
```

## 🔧 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| LLM_API_KEY | DeepSeek API Key（或任意 OpenAI 兼容接口 Key） | - |
| LLM_BASE_URL | LLM 接口地址 | https://api.deepseek.com |
| LLM_MODEL | 大模型名称 | deepseek-v4-flash |
| LLM_MAX_TOKENS | 生成最大 token 数（deepseek-v4-flash 等 reasoning 模型的 reasoning_content 会吃预算，不设上限可能返回空 content；评测实测 1024 稳定） | 1024 |
| EMBEDDING_MODEL | Embedding 模型（本地 HuggingFace） | BAAI/bge-small-zh-v1.5 |
| VECTOR_DB_PATH | 向量数据库路径 | ./data/vector_db |
| DB_PATH | 对话数据库路径 | ./data/history_chat.db |
| MAX_HISTORY | 注入 LLM 上下文的历史消息条数 | 10 |
| FILTERED_SCORE_RATIO | 防跨人物污染阈值（见「评测」，train 子集标定、holdout 验证，1.25 最优） | 1.25 |
| RAG_TOP_K | 检索返回给 LLM 的史料条数（`_retrieve_knowledge` 默认 k） | 3 |
| MULTI_TOP_K | 多人物联合检索返回条数（点名 ≥2 人或枚举题走 multi 分支时用，覆盖期望 3-7 人；评测 multi 子集按此口径算 Recall） | 7 |
| RETRIEVAL_MODE | 检索模式：`similarity`（稠密）\| `hybrid`（稠密+BM25 词法 RRF 融合召回，见「评测」） | similarity |
| HYBRID_BM25_K | 混合检索中 BM25 词法侧候选条数 | 30 |
| HYBRID_RRF_K | 混合检索 RRF 融合常数（与重排器同口径） | 60 |
| CONVERSATION_RETENTION_DAYS | 对话保留天数，超过则由 `scripts/cleanup_db.py` 清理；0=不清理 | 0 |
| RERANK_MODE | 检索重排：`hybrid`（jieba+TF-IDF 词法与稠密向量 RRF 融合，完全离线）\| `cross_encoder`（bge-reranker，需本地缓存）\| `none` | hybrid |
| RERANK_K_FETCH | 重排前候选池大小（先召回 k_fetch 条再精排取 top-k） | 15 |
| STRONG_GLOBAL_THRESHOLD | 决策门1：全局强相关阈值 | 0.70 |
| GAP_THRESHOLD | 决策门1：过滤结果明显劣于全局的距离差阈值 | 0.10 |
| PERSONA_FALLBACK | 双轨开关：`true`（默认）persona 可检索但标注「内置摘要·非权威」且真实史源优先；`false`（严格模式）persona 完全移出史实检索，仅真实史源可检索/引用 | true |
| LLM_PRICE_IN / LLM_PRICE_OUT | LLM 计费价格（¥/1M token，仅用于离线成本估算脚本，非真实计费） | 1.0 / 2.0 |

## 📜 史料数据说明

知识库为**双轨数据源**（详见 [DATA_SOURCES.md](DATA_SOURCES.md)）：

- **真实史源（`doc_type=historical`）**：古诗文网（gushiwen.cn）古籍原文节选（主源，
  已全量入库）、ctext.org 古籍原文、**百度百科**（21 篇，补齐无正史列传/章节未映射
  人物，三手资料如实标注），带 **朝代·书·篇卷** 标注（如春秋·《史记·孔子世家》），
  可作引用溯源依据。**97/97 人均有 historical 文件**（107 篇 historical + 99 篇 persona）；
- **Persona（`doc_type=persona`）**：内置大模型生成摘要（99 篇 `_内置` 后缀），
  仅作语言风格参考/角色设定，**不作为事实依据**，引用时标注「（内置摘要·非权威史源）」。

引用格式：史料块头显示 `出处: 春秋·《史记·孔子世家》 - 古诗文网（gushiwen.cn）`，
footer `【参考史料】[1]《史记·孔子世家》- 春秋·古诗文网（gushiwen.cn)`；
`PERSONA_FALLBACK=off` 时 persona 完全退出史实检索。97 人→数据源映射表见
`data/sources/character_sources.json`（聚焦 97 人，不抓全量《二十四史》）。网络实测：
ctext.org 被反爬 403 封锁、中文维基不可达，故古籍原文源切换为**古诗文网**（见
DATA_SOURCES.md「网络实测与源切换」）。

```bash
# 离线打印 97 人抓取计划（URL 清单，不联网）；去掉 --dry-run 即全量抓取
python scripts/crawl_knowledge.py --dry-run
python scripts/crawl_knowledge.py --sources all      # gushiwen 原文 + 中文维基
python scripts/crawl_knowledge.py --sources gushiwen # 仅古诗文网原文（本环境已跑通）
python scripts/crawl_knowledge.py --characters 李白,孔子
```

## 📏 评测

两套标注评测集（**198 条**，含 train/holdout 分层）+ 检索/延迟/端到端/在线生成脚本：

```bash
# 基础集（26 条：问自己/问他人/问事件，含"当事人自传是陷阱"用例）
python scripts/evaluate_retrieval.py          # hit@1/hit@3/MRR + 防污染门决策正确率
python scripts/evaluate_retrieval.py --sweep  # 阈值扫描（FILTERED_SCORE_RATIO=1.25 即由此标定）
python scripts/evaluate_retrieval.py --llm-grounding 5   # 可选：真实 LLM 引用校验（付费）

# 扩展集（198 条：单相关 145 / 多相关枚举 31 / 库外负面 22，train 159 / holdout 39）
python scripts/evaluate_retrieval_full.py          # hit@k / MRR / 决策正确率 / 多相关 Recall@7 / RAGAS 上下文指标 / 库外拒绝率
python scripts/evaluate_retrieval_full.py --split train      # 只在 train 子集评测（阈值重标定）
python scripts/evaluate_retrieval_full.py --split holdout    # 泛化指标只在此上报
python scripts/evaluate_retrieval_full.py --sweep --split train  # 阈值扫描（train 标定）
RETRIEVAL_MODE=hybrid python scripts/evaluate_retrieval_full.py  # 混合检索（BM25×稠密）对比

# 延迟/成本剖析（离线）：分阶段 p50/p90/mean（检索/重排/LLM 估算/一次性成本）
python scripts/benchmark_retrieval.py --limit 20
python scripts/benchmark_retrieval.py --limit 20 --out bench.json   # 结果落盘

# 端到端评测：Mock LLM 离线跑通完整 chat 链路（路由/引用 grounding/延迟），--llm live 调真实模型（已实跑，见 RAG_EVALUATION_REPORT_FINAL.md §3.4）
python scripts/evaluate_end_to_end.py
python scripts/evaluate_end_to_end.py --bad-cite   # 验证越界引用被丢弃
python scripts/evaluate_end_to_end.py --llm live   # 真实模型（需 .env 配置 DeepSeek key）

# 在线生成评测（RAGAS 风格，真实 LLM，需 .env DeepSeek key；--cache 增量落盘可续跑）
python scripts/evaluate_generation.py --limit 8 --cache /tmp/gen_cache.json   # 冒烟
python scripts/evaluate_generation.py --cache /tmp/gen_cache.json             # 全量 198 条
python scripts/evaluate_generation.py --split holdout --cache ...             # 只看 holdout
# 输出 Faithfulness / Answer Relevancy / Citation Accuracy / 引用覆盖率 / JSON 解析失败率
```

**当前实测**（检索层确定性离线、生成层真实 DeepSeek-v4-flash）：
- 检索层：多相关 Recall@7 **0.745**；库外拒绝 **22/22**、自传注入 0/22；单相关 hit@1 0.897 / MRR 0.933 / 决策正确率 0.986；单元测试 114/114；
- 生成层（50 条代表性抽样）：Faithfulness **0.636**（非负类 **0.723**）/ Answer Relevancy 0.604 / Citation Accuracy 0.735 / 引用覆盖率 0.880；
- e2e live 结构化引用：带【参考史料】引用 **18/20（90%）**、越界引用丢弃 0、路由 20/20。

详细指标、口径与优化过程见 [RAG_EVALUATION_REPORT_FINAL.md](RAG_EVALUATION_REPORT_FINAL.md)。

### 📄 多格式文档解析

知识库不再只认 `*.txt`：`src/retrievers/document_loader.py` 支持
**txt / md / html / pdf / docx / xml / json / csv / tsv / xlsx** 统一解析为 `Document`
（前置头 `【来源】【URL】【人物】【分类】` 及来源标注 `【朝代】【出处】【篇卷】` +
`---` 正文分隔、按文件名推断人物、别名补全、doc_type 自动判定 persona/historical、
朝代从人物配置补齐，与既有 txt 语义一致）；
扫描版 PDF（无文本层）与未知扩展名自动跳过（不支持 OCR）。新知识入库：

```bash
# 增量：只加新文档（按 file 元数据去重，幂等，重复执行不翻倍）
python scripts/ingest_documents.py --src data/documents_sample
# 全量重建（先清空再按 data/knowledge 全部格式重建）
python scripts/ingest_documents.py --src data/knowledge --mode rebuild
```

样例语料见 `data/documents_sample/`（md / html / json / csv，库外人物「张衡」）。

## ✅ 引用可验证

有史料命中时，模型被要求输出结构化 JSON `{"reply": ..., "cited_sources": [索引]}`，
代码侧校验索引落在本次检索集合内才渲染为【参考史料】，越界引用一律丢弃；
解析失败自动回退纯文本，不阻塞对话。因此"引用不存在的文献"不会进入渲染/落库
（详见 `src/agents/history_agent.py` 的 `_parse_structured_reply` / `_validate_cited`）。

## ⚠️ 部署注意

- **默认无鉴权**，仅适合个人 / 内网演示；公网部署请自行加鉴权，并保持 `enableXsrfProtection` 开启。
- 冷启动需加载本地 Embedding（首次联网下载，之后走本地缓存）。
- 更换 Embedding 模型后须删除 `data/vector_db` 并运行 `scripts/build_vector_db.py` 重建。
- 对话库可按保留天数由 `scripts/cleanup_db.py` 清理（建议 cron 定时执行）。

## 📄 License

MIT © 2024 Dreamlee0
