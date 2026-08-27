# 🏛️ 历史人物对话系统（history-rag-chat）

[English](README.en.md) | 中文

> 基于 **LangChain + RAG** 的历史人物对话系统：与中国历史人物进行沉浸式、可溯源的多轮对话。

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![LangChain](https://img.shields.io/badge/LangChain-1.2-green.svg)](https://langchain.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📸 项目预览

### 🎭 人物选择界面

<div align="center">
  <img src="images/chat界面.png" alt="人物选择界面" width="800"/>
</div>

### 💬 对话展示界面

<div align="center">
  <img src="images/对话展示.png" alt="对话展示界面" width="800"/>
</div>

### 🖥️ 聊天界面

<div align="center">
  <img src="images/人物选择.png" alt="聊天界面" width="800"/>
</div>

## ✨ 功能特点

- 🎭 **角色扮演** · 97 位历史人物，覆盖 21 个朝代（三国拆蜀汉/东吴/曹魏），真实还原人物性格与口吻
- 📚 **RAG 知识增强** · 基于真实史料回答，知识可溯源、引用可验证
- 💬 **多轮对话记忆** · SQLite 持久化，刷新不丢失
- 📤 **对话导出** · Markdown / PDF
- 📏 **内置评测体系** · 标注评测集 + hit@k / MRR / 阈值标定，防跨人物污染可量化

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
│   ├── knowledge/           # 史料知识库（99 篇）
│   ├── eval/                # 标注评测集
│   └── vector_db/           # Chroma向量数据库
├── scripts/                 # 工具脚本
├── src/
│   ├── agents/              # 对话编排 / RAG 检索
│   ├── characters/          # 人物管理器
│   ├── database/            # SQLite数据库
│   ├── memory/              # 对话记忆
│   └── retrievers/          # 向量检索
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
| EMBEDDING_MODEL | Embedding 模型（本地 HuggingFace） | BAAI/bge-small-zh-v1.5 |
| VECTOR_DB_PATH | 向量数据库路径 | ./data/vector_db |
| DB_PATH | 对话数据库路径 | ./data/history_chat.db |
| MAX_HISTORY | 注入 LLM 上下文的历史消息条数 | 10 |
| FILTERED_SCORE_RATIO | 防跨人物污染阈值（见「评测」） | 1.20 |
| RETRIEVAL_MODE | 检索模式：`similarity` \| `mmr`（最大边际相关重排） | similarity |
| CONVERSATION_RETENTION_DAYS | 对话保留天数，超过则由 `scripts/cleanup_db.py` 清理；0=不清理 | 0 |

## 📏 评测

标注集 `data/eval/retrieval_eval.json`（26 条：问自己 / 问他人 / 问事件，含"当事人自传是陷阱"的用例）+ 脚本 `scripts/evaluate_retrieval.py`：

```bash
python scripts/evaluate_retrieval.py          # hit@1/hit@3/MRR + 防污染门决策正确率
python scripts/evaluate_retrieval.py --sweep  # 阈值扫描（FILTERED_SCORE_RATIO=1.20 即由此标定）
python scripts/evaluate_retrieval.py --llm-grounding 5   # 可选：真实 LLM 引用校验（付费）
```

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
