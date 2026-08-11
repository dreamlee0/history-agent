# 🏛️ 历史人物对话 Agent

> 基于 LangChain + RAG 的历史人物对话系统，可以与中国历史人物进行沉浸式对话。

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![LangChain](https://img.shields.io/badge/LangChain-0.2+-green.svg)](https://langchain.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📸 项目预览

### 🎭 人物选择界面

<div align="center">
  <img src="images/人物选择.png" alt="人物选择界面" width="800"/>
</div>

### 💬 对话展示界面

<div align="center">
  <img src="images/对话展示.png" alt="对话展示界面" width="800"/>
</div>

### 🖥️ 聊天界面

<div align="center">
  <img src="images/chat界面.png" alt="聊天界面" width="800"/>
</div>

---

## ✨ 功能特点

- 🎭 **角色扮演** - 97位历史人物，覆盖20个朝代，真实还原人物性格和说话风格
- 📚 **RAG知识增强** - 基于真实史料回答问题，支持知识溯源
- 💬 **多轮对话** - 支持上下文记忆，连贯对话
- 💾 **对话持久化** - SQLite 存储对话历史，刷新不丢失
- 📤 **对话导出** - 支持Markdown/PDF格式导出
- 🌐 **Web界面** - 水墨丹青风格的Streamlit界面

## 🚀 快速开始

### 在线体验

访问 Streamlit Cloud 部署的应用即可体验。

### 本地运行

```bash
# 克隆项目
git clone https://github.com/dreamlee0/history-agent.git
cd history-agent

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑.env文件，填入智谱AI API Key

# 启动应用
streamlit run web/app.py
```

本地访问：http://localhost:8501
在线访问：[history-agent.streamlit.app/](https://history-agent.streamlit.app/)

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **Agent框架** | LangChain |
| **大语言模型** | 智谱AI GLM-4 |
| **向量数据库** | Chroma |
| **对话存储** | SQLite |
| **Web界面** | Streamlit |
| **Embedding** | 智谱AI Embedding-3 |

## 📁 项目结构

```
history-agent/
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
│   ├── knowledge/           # 史料知识库
│   └── vector_db/           # Chroma向量数据库
├── scripts/                 # 工具脚本
├── src/
│   ├── agents/              # 对话Agent
│   ├── characters/          # 人物管理器
│   ├── database/            # SQLite数据库
│   ├── loaders/             # 文档加载器
│   ├── memory/              # 对话记忆
│   └── retrievers/          # 向量检索
├── web/
│   ├── app.py               # 主应用
│   ├── styles.py            # 水墨丹青样式
│   └── export_utils.py      # 导出工具
├── images/                  # 项目截图
└── requirements.txt
```

## 📚 历史人物列表（97位）

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
| LLM_API_KEY | 智谱AI API Key（或任意 OpenAI 兼容接口 Key） | - |
| LLM_BASE_URL | LLM 接口地址 | https://open.bigmodel.cn/api/paas/v4 |
| LLM_MODEL | 大模型名称 | glm-4.5-flash |
| EMBEDDING_MODEL | Embedding模型（本地 HuggingFace） | BAAI/bge-small-zh-v1.5 |
| VECTOR_DB_PATH | 向量数据库路径 | ./data/vector_db |
| DB_PATH | 对话数据库路径 | ./data/history_chat.db |

## 📄 License

MIT License © 2024 Dreamlee0
