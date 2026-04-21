#!/bin/bash

# 历史人物对话Agent启动脚本

echo "========================================"
echo "  历史人物对话 Agent"
echo "========================================"

# 检查.env文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到.env文件，正在从模板创建..."
    cp .env.example .env
    echo "📝 请编辑.env文件，填入你的OpenAI API Key"
    exit 1
fi

# 启动应用
echo "🚀 启动Web应用..."
streamlit run web/app.py
