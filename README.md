# 历史人物对话 Agent

基于 LangChain + RAG 的历史人物对话系统，可以与中国历史人物进行沉浸式对话。

## 功能特点

- 🎭 **角色扮演** - 83位历史人物，真实还原人物性格和说话风格
- 📚 **RAG知识增强** - 基于真实史料回答问题，支持知识溯源
- 💬 **多轮对话** - 支持上下文记忆，连贯对话
- 📤 **对话导出** - 支持Markdown/PDF格式导出
- 🌐 **Web界面** - 水墨丹青风格的Streamlit界面

## 在线体验

访问 Streamlit Cloud 部署的应用即可体验。

## 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑.env文件，填入智谱AI API Key

# 启动应用
streamlit run web/app.py
```

## 技术栈

- **LangChain** - Agent框架
- **智谱AI GLM-4** - 大语言模型
- **Chroma** - 向量数据库
- **Streamlit** - Web界面
